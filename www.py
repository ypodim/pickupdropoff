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

    def get_key(self, key):
        week = datetime.date.today().isocalendar().week
        return f"w{week}-{key}"
    def get_week(self, key):
        return key.split('-')[0]

    def get_all(self):
        week = datetime.date.today().isocalendar().week
        result = {}
        for k,v in self._store.items():
            w, key = k.split('-')
            if w == f"w{week}":
                result[key] = v
        return result

    def insert(self, key, val, now=None):
        key = self.get_key(key)
        self._store[key] = val
    def delete(self, key):
        key = self.get_key(key)
        if key in self._store:
            del self._store[key]

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
]

class DropdownOptionsHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(DROPDOWN_OPTIONS))

class SelectionHandler(tornado.web.RequestHandler):
    def initialize(self, manager):
        self.manager = manager

    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(self.manager.get_all()))

    def post(self):
        data = json.loads(self.request.body)
        field_id = data.get("id")
        value = data.get("value")
        option = next(filter(lambda opt: str(opt["value"]) == str(value), DROPDOWN_OPTIONS), None)
        name = option["name"] if option else None
        if field_id:
            if option is None:
                self.manager.delete(field_id)
            else:
                self.manager.insert(field_id, value)
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
    http_server = tornado.httpserver.HTTPServer(app)#, ssl_options={
        # "certfile": "keys/localhost.pem",
        # "keyfile": "keys/localhost-key.pem",
    # })
    http_server.listen(8888, address="127.0.0.1")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("exiting")
