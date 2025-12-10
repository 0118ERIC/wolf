from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import random

app = Flask(__name__)
app.secret_key = "secret"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

players = {}
alive = set()
votes = {}
night_actions = {}
game_phase = "waiting"
chat_messages = []
night_result = ""

roles = ["wolf", "seer", "villager", "villager"]

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/join', methods=['POST'])
def join():
    name = request.form['name']
    if name in players:
        return jsonify({"status":"error","msg":"名字已被使用"})
    players[name] = None
    alive.add(name)
    session['name'] = name
    return jsonify({"status":"ok"})

@app.route('/start', methods=['POST'])
def start():
    global players, roles, game_phase
    if len(players) < 3:
        return jsonify({"status":"error","msg":"至少需要 3 名玩家"})
    shuffled_roles = random.sample(roles, len(players))
    for i,p in enumerate(players):
        players[p] = shuffled_roles[i]
    game_phase = "night"
    return jsonify({"status":"ok"})

@app.route('/action', methods=['POST'])
def action():
    global night_actions, votes
    name = session.get('name')
    target = request.form['target']
    if game_phase == "night":
        if players[name] in ["wolf","seer"]:
            night_actions[name] = target
    elif game_phase == "day":
        if name in alive:
            votes[name] = target
    return jsonify({"status":"ok"})

@app.route('/status')
def status():
    global game_phase, night_actions, votes, night_result
    required_roles = ["wolf","seer"]

    # 夜晚：只等狼或預言家操作
    if game_phase=="night" and all(p not in alive or (players[p] not in required_roles or p in night_actions) for p in alive):
        night_result=""
        wolf_targets = [t for p,t in night_actions.items() if players[p]=="wolf"]
        if wolf_targets:
            victim=random.choice(wolf_targets)
            if victim in alive:
                alive.remove(victim)
                night_result+=f"{victim} 被狼人殺死。"
        for p,t in night_actions.items():
            if players[p]=="seer":
                role = players.get(t,"未知")
                night_result+=f" 預言家驗 {t} 的身份是 {role}。"
        night_actions={}
        votes={}
        game_phase="day"

    # 白天
    elif game_phase=="day" and len(votes)==len(alive):
        tally={}
        for v in votes.values():
            tally[v]=tally.get(v,0)+1
        if tally:
            max_votes=max(tally.values())
            out_players=[p for p,c in tally.items() if c==max_votes]
            out_player=random.choice(out_players)
            if out_player in alive:
                alive.remove(out_player)
                night_result=f"{out_player} 被投票出局。"
        votes.clear()
        game_phase="night"

    # 勝利判定
    wolves=[p for p in alive if players[p]=="wolf"]
    villagers=[p for p in alive if players[p]!="wolf"]
    winner=None
    if not wolves:
        winner="村民勝利"
        game_phase="ended"
    elif len(wolves)>=len(villagers):
        winner="狼人勝利"
        game_phase="ended"

    name=session.get('name')
    identity=players.get(name,"未知")
    return jsonify({
        "phase":game_phase,
        "identity":identity,
        "alive":list(alive),
        "chat":chat_messages,
        "night_result":night_result,
        "winner":winner
    })

@app.route('/chat', methods=['POST'])
def chat():
    name=session.get('name')
    msg=request.form['msg']
    chat_messages.append(f"{name}: {msg}")
    return jsonify({"status":"ok"})

# Render 用 Gunicorn 啟動，不需要 debug
if __name__=="__main__":
    app.run(host="0.0.0.0")
