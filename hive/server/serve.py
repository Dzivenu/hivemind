# -*- coding: utf-8 -*-
import json
import logging
import os
from datetime import datetime

import bottle
import hive.server.methods as rpcmethods
from bottle import abort, request
from bottle_errorsrest import ErrorsRestPlugin
from bottle_sqlalchemy import Plugin
from hive.db.schema import metadata as hive_metadata
from hive.sbds.jsonrpc import register_endpoint
from hive.sbds.sbds_json import ToStringJSONEncoder
from sqlalchemy import create_engine



from hive.db.methods import (
    db_head_state,
    get_followers,
    get_following,
    following_count,
    follower_count,
    get_user_feed,
    get_blog_feed,
    get_discussions_by_sort_and_tag,
    get_related_posts,
    payouts_total,
    payouts_last_24h,
)


logger = logging.getLogger(__name__)

app = bottle.Bottle()
app.config['hive.MAX_BLOCK_NUM_DIFF'] = 10
app.config['hive.MAX_DB_ROW_RESULTS'] = 100000
app.config['hive.DB_QUERY_LIMIT'] = app.config['hive.MAX_DB_ROW_RESULTS'] + 1
app.config['hive.logger'] = logger

app.install(
    bottle.JSONPlugin(json_dumps=lambda s: json.dumps(s, cls=ToStringJSONEncoder)))
app.install(ErrorsRestPlugin())


# Non JSON-RPC routes
# -------------------
@app.get('/health')
def health():
    state = db_head_state()
    if state['db_head_age'] > app.config['hive.MAX_BLOCK_NUM_DIFF'] * 3:
        abort(
            500,
            'head block age (%ss) > max allowable (%ss); head block num: %s'
            % (state['db_head_age'], app.config['hive.MAX_BLOCK_NUM_DIFF'] * 3,
                state['db_head_block']))
    else:
        return dict(
            state=state,
            timestamp=datetime.utcnow().isoformat())

@app.get('/head_state')
def callback():
    return db_head_state()

@app.get('/stats/payouts')
def callback():
    return dict(total = payouts_total(), last_24h = payouts_last_24h())


# discussions
# -----------

def get_context():
    if 'context' in request.query:
        return request.query['context']

@app.get('/blog/<user>/<skip>')
def callback(user, skip):
    return dict(user = user, posts = get_blog_feed(user, int(skip), 20, get_context()))

@app.get('/feed/<user>/<skip>')
def callback(user, skip):
    return dict(user = user, posts = get_user_feed(user, int(skip), 20, get_context()))

@app.get('/discussions/sort/<sort>/<skip>')
def callback(sort, skip):
    return dict(posts = get_discussions_by_sort_and_tag(sort, None, int(skip), 20, get_context()))

@app.get('/discussions/tag/<tag>/sort/<sort>/<skip>')
def callback(tag, sort, skip):
    return dict(posts = get_discussions_by_sort_and_tag(sort, tag, int(skip), 20, get_context()))

@app.get('/related/<account>/<permlink>')
def callback(account, permlink):
    return dict(posts = get_related_posts(account, permlink))


# follows
# -------

@app.get('/followers/<user>')
def callback(user):
    return dict(user = user, followers = get_followers(user))

@app.get('/followers/<user>/<skip>/<limit>')
def callback(user, skip, limit):
    return dict(user = user, followers = get_followers(user, skip, limit))



# JSON-RPC route
# --------------
jsonrpc = register_endpoint(path='/', app=app, namespace='hive')

json_rpc_methods = {
    'head_state': db_head_state,
    'get_followers': rpcmethods.get_followers,
    'get_following': rpcmethods.get_following,
}
for method_name, fn_call in json_rpc_methods.items():
    jsonrpc.register_method(method=fn_call, method_name=method_name)

# WSGI application
# ----------------
application = app


# dev/debug server
# ----------------
def _dev_server(port=8081, debug=True):
    # pylint: disable=bare-except
    try:
        print("Launch hive server.")
        app.run(port=port, debug=debug)
    except:
        logger.exception('HTTP Server Exception')
    finally:
        app.close()


# For pdb debug only
if __name__ == '__main__':
    _dev_server()
