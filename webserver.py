from sanic import response, Sanic

from functools import wraps

import aiohttp
import base64

import json
import os

app = Sanic(__name__)

with open('data/status_codes.json') as f:
    app.status_codes = json.load(f)


def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == os.environ.get('auth-token'):
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator


async def git_commit():
    url = 'https://api.github.com/repos/SharpBit/webserver/contents/data/hq_questions.json'
    base64content = base64.b64encode(open('data/hq_questions.json', 'rb').read())
    async with app.session.get(url + '?ref=master', headers={'Authorization': 'token ' + os.environ.get('github-token')}) as resp:
        data = await resp.json()
        sha = data['sha']
    if base64content.decode('utf-8') + '\n' != data['content']:
        message = json.dumps({
            'message': 'Update question list.',
            'branch': 'master',
            'content': base64content.decode('utf-8'),
            'sha': sha
        })

        async with session.put(url, data=message, headers={'Content-Type': 'application/json', 'Authorization': 'token ' + os.environ.get('github-token')}) as resp:
            print(resp)
    else:
        print('Nothing to update.')


@app.listener('before_server_start')
async def create_session(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)


@app.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()


@app.route('/')
async def index(request):
    return response.json({'hello': 'world'})


@app.route('/status/<status>')
async def status_code(request, status):
    try:
        info = app.status_codes[status]
    except KeyError:
        return response.json({'error': True, 'status': status, 'message': 'invalid status'})
    else:
        return response.json({'error': False, 'status': status, 'info': info})


@app.route('/hq')
async def hq_home(request):
    return response.json({
        'endpoints': {
            'GET': ['questions'],
            'POST': ['answer', 'question']
        }
    })


@app.route('/hq/questions')
async def load_questions(request):
    with open('data/hq_questions.json') as f:
        questions = json.load(f)
    return response.json(questions)


@app.route('/hq/question', methods=['POST'])
@authorized()
async def submit_question(request):
    data = request.json
    checks = ['question', 'questionNumber', 'time', 'category']

    # gotta handle bad requests amirite
    if not all([True if k in data.keys() else False for k in checks]):
        return response.json({'error': True, 'message': 'Enter a question, question number, epoch time, and category.'}, 400)

    with open('data/hq_questions.json', 'r+') as f:
        questions = json.load(f)
        questions.append(data)
        f.seek(0)
        json.dump(questions, f, indent=4)
    return response.json({'error': False, 'message': 'Question successfully submitted'})


@app.route('/hq/answer', methods=['POST'])
@authorized()
async def submit_answer(request):
    checks = ['question', 'answers', 'final']
    if not all([True if k in request.json.keys() else False for k in checks]):
        return response.json({'error': True, 'message': 'Enter a question, answers, and final question (true/false)'}, 400)

    with open('data/hq_questions.json', 'r+') as f:
        questions = json.load(f)
        for q in questions:
            if request.json['question'] == q['question']:
                q['answers'] = request.json['answers']
        f.seek(0)
        json.dump(questions, f, indent=4)
    if request.json['final']:
        await git_commit()
    return response.json({'error': False, 'message': 'Answer successfully submitted'})


if __name__ == '__main__':
    app.run(port=os.getenv('PORT'))
