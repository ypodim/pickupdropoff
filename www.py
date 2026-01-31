import asyncio
import tornado.web
import tornado.websocket
import tornado.httpserver
import os
import json
import time
import datetime

class Store(object):
    def __init__(self, name="store"):
        self.name = name.strip()
        self._store = {}
        self._last_save = 0
        self.buffer = []
        self.filename = "data_%s.json" % self.name
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                self._store = json.load(f)

    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self._store, f)

    def persist(self):
        now = time.time()
        if now - self._last_save > 1:
            self.save()
            self._last_save = now

    def get_all(self, week):
        week_key = str(week)
        return self._store.get(week_key, {})

    def insert(self, week, key, val):
        week_key = str(week)
        if week_key not in self._store:
            self._store[week_key] = {}
        self._store[week_key][key] = val

    def delete(self, week, key):
        week_key = str(week)
        if week_key in self._store and key in self._store[week_key]:
            del self._store[week_key][key]

class DefaultHandler(tornado.web.RequestHandler):
    def initialize(self, manager):
        self.manager = manager
    def get(self):
        self.render("index.html")

# Dropdown options - single source of truth
DROPDOWN_OPTIONS = [
    dict(value=1, name="Pol", daughter="Elsa"),
    dict(value=2, name="Rick", daughter="Brooke"),
    dict(value=3, name="Sarah F", daughter="Brooke"),
    dict(value=4, name="Sarah S", daughter="Mia"),
    dict(value=5, name="Hannah", daughter="Ella"),
    dict(value=6, name="Bettina", daughter="Elsa"),
    dict(value=7, name="Greg", daughter="Ella"),
]

class DropdownOptionsHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(DROPDOWN_OPTIONS))

class SelectionHandler(tornado.web.RequestHandler):
    def initialize(self, manager):
        self.manager = manager

    def get(self):
        week = self.get_argument("week", None)
        if week:
            week = int(week)
        else:
            week = datetime.date.today().isocalendar().week
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(self.manager.get_all(week)))

    def post(self):
        data = json.loads(self.request.body)
        field_id = data.get("id")
        value = data.get("value")
        week = data.get("week")
        if week:
            week = int(week)
        else:
            week = datetime.date.today().isocalendar().week

        if week < datetime.date.today().isocalendar().week:
            print("can't edit the past")
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"status": "not editable"}))
            return

        option = next(filter(lambda opt: str(opt["value"]) == str(value), DROPDOWN_OPTIONS), None)
        name = option["name"] if option else None
        if field_id:
            if option is None:
                self.manager.delete(week, field_id)
            else:
                self.manager.insert(week, field_id, value)
            self.manager.persist()
            print(f"Selection updated: {field_id} = {name} {option}")

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"status": "ok"}))

class LiveSocket(tornado.websocket.WebSocketHandler):
    clients = set()
    def initialize(self, manager):
        self.manager = manager

    def open(self):
        LiveSocket.clients.add(self)

    def on_message(self, message):
        # self.write_message(u"You said: " + message)
        print("got", message)

    def on_close(self):
        LiveSocket.clients.remove(self)

    @classmethod
    def send_message(cls, message: str):
        # print(f"Sending message {message} to {len(cls.clients)} client(s).")
        for client in cls.clients:
            client.write_message(message)


class Application(tornado.web.Application):
    def __init__(self, manager):
        handlers = [
            (r"/api/dropdown-options", DropdownOptionsHandler),
            (r"/api/selection", SelectionHandler, dict(manager=manager)),
            (r"/ws", LiveSocket, dict(manager=manager)),
            (r'/favicon.ico', tornado.web.StaticFileHandler),
            (r'/static/', tornado.web.StaticFileHandler),
            (r"/.*", DefaultHandler, dict(manager=manager)),

        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "html"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=True,
        )
        super(Application, self).__init__(handlers, **settings)

async def main():
    manager = Store()
    app = Application(manager)
    http_server = tornado.httpserver.HTTPServer(app)
    # http_server.listen(8181, address="127.0.0.1")
    http_server.listen(8181)
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("exiting")
