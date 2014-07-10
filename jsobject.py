import time
from IPython.kernel.comm import Comm
from IPython.display import display, Javascript
import uuid
import json
import tornado.web

object_registry = {} # GUID -> Instance
callback_registry = {} # GUID -> Callback

ip = get_ipython()

class Delayed(object):
    def __init__(self):
        self._cached = None
        self._callback = None
        
    def __call__(self, callback):
        self._callback = callback
        self._try_run()
        
    def invoke(self, *pargs, **kwargs):
        self._cached = (pargs, kwargs)
        self._try_run()
        
    def _try_run(self):
        if self._cached is not None and self._callback is not None:
            self._callback(*self._cached[0], **self._cached[1])

    def wait_for(self, timeout=3000):
        results = [None]
        results_called = [False]
        
        def results_callback(val):
            results[0] = val
            results_called[0] = True
        self(results_callback)
        
        start = time.time()
        while not results_called[0]:
            if time.time() - start > timeout / 1000.:
                raise Exception('Timeout of %d ms reached' % timeout)
            ip.kernel.do_one_iteration()
        return results[0]


class AJAXHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ('POST', 'GET')

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")

    def post(self):
        AJAXHandler.value = self.get_argument('value')

    def get(self):
        response = {'turkey': 'lol'}
        #response['value'] = AJAXHandler.value
        self.write(json.dumps(response))


class BrowserContext(object):
    def __init__(self, port=9988):
        # Start the tornado server.
        application = tornado.web.Application([
            (r"/", AJAXHandler),
        ])
        application.listen(port)

        with open('jsobject.js') as f:
            display(Javascript('var ajax_port = %d;\n' % port + f.read()))

        self._calls = 0
        self._callbacks = {}
        self._browser_context = Comm(target_name='BrowserContext')
        self._browser_context.on_msg(self._on_msg)
        
    def _on_msg(self, msg):
        data = msg['content']['data']
        if 'callback' in data:
            guid = data['callback']
            callback = callback_registry[guid]
            args = data['arguments']
            args = [self.parse_object(a) for a in args]
            index = data['index']

            results = callback(*args)
            return self.encode_object(self._send('return', index=index, results=results))
        else:
            index = data['index']
            immutable = data['immutable']
            value = data['value']
            if index in self._callbacks:
                self._callbacks[index].invoke({
                    'immutable': immutable,
                    'value': value
                })
                del self._callbacks[index]
        
    def encode_object(self, obj):
        if hasattr(obj, '_jsid'):
            return {'immutable': False, 'value': obj._jsid}
        else:
            obj_json = {'immutable': True}
            try:
                json.dumps(obj)
                obj_json['value'] = obj
            except:
                pass
            if callable(obj):
                guid = str(uuid.uuid4())
                callback_registry[guid] =  obj
                obj_json['callback'] = guid
            return obj_json
        
    def parse_object(self, obj):
        if obj['immutable']:
            return obj['value']
        else:
            guid = obj['value']
            if not guid in object_registry:
                instance = JSObject(self, guid)
                object_registry[guid] = instance
            return object_registry[guid]

    def getattr(self, parent, child):
        return self._send('getattr', parent=parent, child=child)
        
    def setattr(self, parent, child, value):
        return self._send('setattr', parent=parent, child=child, value=value)
        
    def apply(self, parent, function, *pargs):
        return self._send('apply', parent=parent, function=function, args=pargs)
        
    def _send(self, method, **parameters):
        msg = {
            'index': self._calls,
            'method': method, 
        }
        msg.update(parameters)
        
        delayed = Delayed()
        self._callbacks[self._calls] = delayed
        
        self._calls += 1
        self._browser_context.send(msg)
        
        return delayed
    

class JSObject(object):
    def __init__(self, context = None, jsid=''):
        if context is None:
            context = BrowserContext()
        self.__dict__['_context'] = context
        self.__dict__['_jsid'] = jsid
        self.__dict__['_last_jsid'] = ''
        
    def __getattr__(self, name):
        results = self._context.parse_object(self._context.getattr(self._jsid, name).wait_for())
        if isinstance(results, JSObject):
            results.__dict__['_last_jsid'] = self._jsid
        return results
    
    def __setattr__(self, name, value):
        results = self._context.setattr(self._jsid, name, self._context.encode_object(value)).wait_for()
        if not results['value']:
            raise Exception('Set attribute failed.')
    
    def __call__(self, *pargs):
        args = [self._context.encode_object(p) for p in pargs]
        return self._context.parse_object(self._context.apply(self._last_jsid, self._jsid, *args).wait_for())
