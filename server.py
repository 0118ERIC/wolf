from flask import Flask, render_template, request, jsonify, session
import random
import threading

app = Flask(__name__)
app.secret_key = "super-secret-key"  # 必須有

# -------------------- 全局遊戲資料 --------------------
players = {}        # 玩家名稱 -> 角色
alive = set()       # 存活玩家
votes = {}          # 白天投票
night_actions = {}  # 夜晚操作
game_phase = "waiting"
chat_messages = []
night_result = ""
lock = threading.Lock()  # 多線程保護全局資料

roles = ["wolf", "seer", "villager", "villager"]

# -------------------- API --------------------

@app.route('/')
def index():
    return render_template("index.html")  # 你的 Brython 前端

@app.route('/join', methods=['POST'])
def join():
    name = request.form.get('name')
    if not name:
        return jsonify({"status":"error","msg":"請輸入名字"})
    with lock:
        if name in players:
            return jsonify({"status":"error","msg":"名字已被使用"})
        players[name] = None
        alive.add(name)
    session['name'] = name
    return jsonify({"status":"ok"})

@app.route('/start', methods=['POST'])
def start():
    global players, roles, game_phase
    with lock:
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
    if not name:
        return jsonify({"status":"error","msg":"請先加入遊戲"})
    target = request.form.get('target')
    if not target:
        return jsonify({"status":"error","msg":"沒有指定目標"})
    with lock:
        if game_phase == "night":
            if players.get(name) in ["wolf","seer"] and target in alive:
                night_actions[name] = target
        elif game_phase == "day":
            if name in alive and target in alive:
                votes[name] = target
    return jsonify({"status":"ok"})

@app.route('/status')
def status():
    global game_phase, night_actions, votes, night_result
    name = session.get('name')
    if not name:
        return jsonify({"status":"error","msg":"請先加入遊戲"})

    with lock:
        required_roles = ["wolf","seer"]

        # 夜晚邏輯
        if game_phase=="night" and all(
            p not in alive or (players.get(p) not in required_roles or p in night_actions) 
            for p in alive
        ):
            night_result=""
            wolf_targets = [t for p,t in night_actions.items() if players.get(p)=="wolf" and t in alive]
            if wolf_targets:
                victim=random.choice(wolf_targets)
                alive.discard(victim)
                night_result+=f"{victim} 被狼人殺死。"
            for p,t in night_actions.items():
                if players.get(p)=="seer" and t in players:
                    role = players.get(t,"未知")
                    night_result+=f" 預言家驗 {t} 的身份是 {role}。"
            night_actions.clear()
            votes.clear()
            game_phase="day"

        # 白天邏輯
        elif game_phase=="day" and len(votes)==len(alive):
            tally={}
            for v in votes.values():
                if v in alive:
                    tally[v]=tally.get(v,0)+1
            if tally:
                max_votes=max(tally.values())
                out_players=[p for p,c in tally.items() if c==max_votes]
                out_player=random.choice(out_players)
                alive.discard(out_player)
                night_result=f"{out_player} 被投票出局。"
            votes.clear()
            game_phase="night"

        # 勝利判定
        wolves=[p for p in alive if players.get(p)=="wolf"]
        villagers=[p for p in alive if players.get(p)!="wolf"]
        winner=None
        if not wolves:
            winner="村民勝利"
            game_phase="ended"
        elif len(wolves)>=len(villagers):
            winner="狼人勝利"
            game_phase="ended"

        identity = players.get(name,"未知")
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
    name = session.get('name')
    if not name:
        return jsonify({"status":"error","msg":"請先加入遊戲"})
    msg = request.form.get('msg')
    if not msg:
        return jsonify({"status":"error","msg":"訊息為空"})
    with lock:
        chat_messages.append(f"{name}: {msg}")
    return jsonify({"status":"ok"})

# -------------------- 啟動 --------------------
if __name__=="__main__":
    app.run(host="0.0.0.0")
