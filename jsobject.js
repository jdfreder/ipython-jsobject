window.jq = $;

var kernel = IPython.notebook.kernel;
var ws_host = kernel.ws_host;
var ajax_url = 'http:' + ws_host.substr(3).split(':')[0] + ':' + ajax_port + '/';
var make_guid = IPython.utils.uuid;
var is_immutable = function (x) { return !(x instanceof Object); };
var last_cell = null;

var instance_register = {}; // GUID -> Instance

console.log();
console.log(ajax_url);
console.log($.ajax(ajax_url, {async: false}));

var get_guid = function(instance) {
    if (instance._guid === undefined) {
        var guid = make_guid();
        instance._guid = guid;
        instance_register[guid] = instance;
    }
    return instance._guid;
};

var comm_opened = function (comm, msg) {
    var call_count = 0;

    var results_cache = {};

    var send = function(original_msg, content) {
        var cell = IPython.notebook.get_msg_cell(original_msg.parent_header.msg_id) || last_cell;
        last_cell = cell;
        var handle_output = null;
        var handle_clear_output = null;
        if (cell && cell.output_area) {
            handle_output = $.proxy(cell.output_area.handle_output, cell.output_area);
            handle_clear_output = $.proxy(cell.output_area.handle_clear_output, cell.output_area);
        }

        // Create callback dict using what is known
        var callbacks = {
            iopub : {
                output : handle_output,
                clear_output : handle_clear_output,
            },
        };
        comm.send(content, callbacks);
    };

    var encode = function (index, results) {
        var response = null;
        if (is_immutable(results)) {
            response = {
                index: index,
                immutable: true,
                value: results
            };
        } else {
            response = {
                index: index,
                immutable: false,
                value: get_guid(results)
            };
        }
        return response;
    };

    var results_response = function (msg, index, results) {
        if (results === undefined) {
            results = null;
        }
        send(msg, encode(index, results));
    };

    var get_object = function(msg, x, timeout) {
        timeout = timeout || 3000;
        var obj;
        if (x.immutable) {
            obj = x.value;
        } else {
            obj = instance_register[x.value];
        }

        if (x.callback) {

            var callback = function () {
                var encoded = [];
                for (var i = 0; i < arguments.length; i++) {
                    var argument = arguments[i];
                    encoded.push(encode(call_count, argument));
                }
                send(msg, {
                    'callback': x.callback,
                    'index': call_count,
                    'arguments': encoded});

                // TODO
                
                call_count++;
                return null; // TODO: Return value here.
            };

            if (obj === null || obj === undefined) {
                return callback;
            } else {

                // Make the object callable!
                Object.setPrototypeOf(obj, Object.getPrototypeOf(callback));
                Object.setPrototypeOf(callback, obj);
                return callback;
            }

        }
        return obj;
    };

    var get_objects = function(msg, x) {
        var values = [];
        for (var i = 0; i < x.length; i++) {
            values.push(get_object(msg, x[i]));
        }
        return values;
    };

    var on_comm_msg = function(msg) {
        var data = msg.content.data;
        
        // method
        // parent
        // child
        // value
        // args
        // index
        if (data.method == 'getattr') {
            if (data.parent === '') {
                results_response(msg, data.index, window[data.child]);
            } else {
                results_response(msg, data.index, instance_register[data.parent][data.child]);
            }
        } else if (data.method == 'setattr') {
            if (data.parent === '') {
                window[data.child] = get_object(msg, data.value);
            } else {
                instance_register[data.parent][data.child] = get_object(msg, data.value);
            }
            results_response(msg, data.index, true);
        } else if (data.method == 'return') {
            var index = data.index;
            var results = data.results;
            results_cache[index] = results;
        } else if (data.method == 'apply') {
            var parent = window;
            if (data.parent !== '') {
                parent = instance_register[data.parent];
            }
            var instance = instance_register[data.function];
            results_response(msg, data.index, instance.apply(parent, get_objects(msg, data.args)));
        }
    };
    comm.on_msg(on_comm_msg);
};

IPython.notebook.kernel.comm_manager.register_target('BrowserContext', comm_opened);
