from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from config import Config


# from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

#app.config['SECRET_KEY'] = SECRET_KEY

# make current year available in every template
@app.context_processor
def inject_now():
    from datetime import datetime
    return {'current_year': datetime.utcnow().year}

def get_db_connection():
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        port=Config.DB_PORT,
        auth_plugin='mysql_native_password'    # ← force the old plugin
    )


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/groups')
def groups():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT * FROM GroupStandings ORDER BY group_name, points DESC;')
    rows = cur.fetchall()
    conn.close()

    groups = {}
    for r in rows:
        groups.setdefault(r['group_name'], []).append(r)
    return render_template('groups.html', groups=groups)

@app.route('/teams')
def teams():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT team_id, name, founded_year FROM Team ORDER BY name;')
    teams = cur.fetchall()
    conn.close()
    return render_template('teams.html', teams=teams)

@app.route('/players')
def players():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT 
        p.player_id,
        p.name,
        p.position,
        p.jersey_number,
        t.name AS team_name,
        c.name AS country
      FROM Player p
      JOIN Team    t ON p.team_id    = t.team_id
      JOIN Country c ON p.country_id = c.country_id
      ORDER BY p.name;
    """)
    players = cur.fetchall()
    conn.close()
    return render_template('players.html', players=players)

@app.route('/matches')
def matches():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT
        m.match_id,
        m.match_date,
        ts.stage_info AS stage,
        v.name        AS venue,
        GROUP_CONCAT(CONCAT(t.name, ' (', mt.goals_scored, ')') SEPARATOR ' vs ')
          AS score
      FROM Matches m
      JOIN TournamentStage ts ON m.stage_id = ts.stage_id
      JOIN Venue           v  ON m.venue_id = v.venue_id
      JOIN MatchTeam      mt  ON m.match_id = mt.match_id
      JOIN Team           t   ON mt.team_id = t.team_id
      GROUP BY m.match_id
      ORDER BY m.match_date DESC;
    """)
    matches = cur.fetchall()
    conn.close()
    return render_template('matches.html', matches=matches)

# — Admin / Login —

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if (request.form['username']=='admin'
            and request.form['password']=='password'):
            session['admin'] = True
            flash('Logged in successfully')
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out')
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    return render_template('admin.html')

# -------------- TEAMS CRUD --------------

@app.route('/admin/teams')
def admin_teams():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT team_id, name, founded_year FROM Team ORDER BY name")
    teams = cur.fetchall()
    conn.close()
    return render_template('admin_teams.html', teams=teams)

@app.route('/admin/teams/add', methods=['GET','POST'])
def admin_teams_add():
    if request.method=='POST':
        name, year, country = request.form['name'], request.form['founded_year'], request.form['country_id']
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("INSERT INTO Team(name,founded_year,country_id) VALUES(%s,%s,%s)",
                    (name, year, country))
        conn.commit(); conn.close()
        return redirect(url_for('admin_teams'))
    # load countries for select
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT country_id,name FROM Country ORDER BY name")
    countries = cur.fetchall(); conn.close()
    return render_template('admin_team_form.html', countries=countries, action='Add')

@app.route('/admin/teams/edit/<int:id>', methods=['GET','POST'])
def admin_teams_edit(id):
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    if request.method=='POST':
        cur.execute("UPDATE Team SET name=%s,founded_year=%s,country_id=%s WHERE team_id=%s",
                    (request.form['name'],request.form['founded_year'],
                     request.form['country_id'], id))
        conn.commit(); conn.close()
        return redirect(url_for('admin_teams'))
    # GET → load team + countries
    cur.execute("SELECT * FROM Team WHERE team_id=%s", (id,))
    team = cur.fetchone()
    cur.execute("SELECT country_id,name FROM Country ORDER BY name")
    countries = cur.fetchall()
    conn.close()
    return render_template('admin_team_form.html',
                           team=team, countries=countries, action='Edit')

@app.route('/admin/teams/delete/<int:id>')
def admin_teams_delete(id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM Team WHERE team_id=%s", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_teams'))


# ------------- PLAYERS CRUD --------------

@app.route('/admin/players')
def admin_players():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT p.player_id,p.name,
                          p.position,p.jersey_number,
                          t.name AS team_name,
                          c.name AS country_name
                   FROM Player p
                   JOIN Team t ON p.team_id=t.team_id
                   JOIN Country c ON p.country_id=c.country_id
                   ORDER BY p.name""")
    players = cur.fetchall(); conn.close()
    return render_template('admin_players.html', players=players)

@app.route('/admin/players/add', methods=['GET','POST'])
def admin_players_add():
    conn= get_db_connection(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        vals = (request.form['name'],request.form['position'],
                request.form['jersey_number'],
                request.form['team_id'],request.form['country_id'])
        # call your AddPlayer proc
        cur.callproc('AddPlayer', vals)
        conn.commit(); conn.close()
        return redirect(url_for('admin_players'))
    # GET → load teams + countries
    cur.execute("SELECT team_id,name FROM Team ORDER BY name")
    teams = cur.fetchall()
    cur.execute("SELECT country_id,name FROM Country ORDER BY name")
    countries = cur.fetchall()
    conn.close()
    return render_template('admin_player_form.html',
                           teams=teams,countries=countries, action='Add')

@app.route('/admin/players/edit/<int:id>', methods=['GET','POST'])
def admin_players_edit(id):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    if request.method == 'POST':
        cur.execute("""
            UPDATE Player
               SET name=%s,
                   position=%s,
                   jersey_number=%s,
                   team_id=%s,
                   country_id=%s
             WHERE player_id=%s
        """, (
            request.form['name'],
            request.form['position'],
            request.form['jersey_number'],
            request.form['team_id'],
            request.form['country_id'],
            id
        ))
        conn.commit(); conn.close()
        return redirect(url_for('admin_players'))
    # GET: load player + dropdowns
    cur.execute("SELECT * FROM Player WHERE player_id=%s", (id,))
    player = cur.fetchone()
    cur.execute("SELECT team_id,name FROM Team ORDER BY name"); teams=cur.fetchall()
    cur.execute("SELECT country_id,name FROM Country ORDER BY name"); countries=cur.fetchall()
    conn.close()
    return render_template('admin_player_form.html',
                           player=player, teams=teams, countries=countries, action='Edit')

@app.route('/admin/players/delete/<int:id>')
def admin_players_delete(id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM Player WHERE player_id=%s", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_players'))




# ------------- MATCHES CRUD --------------

@app.route('/admin/matches')
def admin_matches():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT m.match_id,
                          m.match_date,
                          ts.stage_info,
                          v.name AS venue
                   FROM Matches m
                   JOIN TournamentStage ts ON m.stage_id=ts.stage_id
                   JOIN Venue v ON m.venue_id=v.venue_id
                   ORDER BY m.match_date DESC""")
    matches = cur.fetchall(); conn.close()
    return render_template('admin_matches.html', matches=matches)

@app.route('/admin/matches/add', methods=['GET','POST'])
def admin_matches_add():
    conn = get_db_connection(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        # call AddMatchWithResults proc
        args = (
          request.form['match_date'],
          request.form['venue_id'],
          request.form['stage_id'],
          request.form['team1_id'],
          request.form['goals1'],
          request.form['result1'],
          request.form['team2_id'],
          request.form['goals2'],
          request.form['result2']
        )
        cur.callproc('AddMatchWithResults', args)
        conn.commit(); conn.close()
        return redirect(url_for('admin_matches'))
    # GET → load form selects
    cur.execute("SELECT venue_id,name FROM Venue ORDER BY name"); venues=cur.fetchall()
    cur.execute("SELECT stage_id,stage_info FROM TournamentStage"); stages=cur.fetchall()
    cur.execute("SELECT team_id,name FROM Team ORDER BY name"); teams=cur.fetchall()
    conn.close()
    return render_template('admin_match_form.html',
                           venues=venues,stages=stages,teams=teams)

@app.route('/admin/matches/edit/<int:id>', methods=['GET','POST'])
def admin_matches_edit(id):
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        # update Matches
        cur.execute("""
            UPDATE Matches
               SET match_date=%s, venue_id=%s, stage_id=%s
             WHERE match_id=%s
        """, (
            request.form['match_date'],
            request.form['venue_id'],
            request.form['stage_id'],
            id
        ))
        # update both MatchTeam rows
        cur.execute("UPDATE MatchTeam SET goals_scored=%s, result=%s WHERE match_id=%s AND team_id=%s",
                    (request.form['goals1'], request.form['result1'], id, request.form['team1_id']))
        cur.execute("UPDATE MatchTeam SET goals_scored=%s, result=%s WHERE match_id=%s AND team_id=%s",
                    (request.form['goals2'], request.form['result2'], id, request.form['team2_id']))
        conn.commit(); conn.close()
        return redirect(url_for('admin_matches'))
    # GET: load match + its two MT rows + dropdowns
    cur.execute("SELECT * FROM Matches WHERE match_id=%s", (id,))
    match = cur.fetchone()
    cur.execute("SELECT team_id,goals_scored AS goals, result FROM MatchTeam WHERE match_id=%s", (id,))
    rows = cur.fetchall()
    match.update({
      'team1_id': rows[0]['team_id'], 'goals1': rows[0]['goals'], 'result1': rows[0]['result'],
      'team2_id': rows[1]['team_id'], 'goals2': rows[1]['goals'], 'result2': rows[1]['result'],
    })
    cur.execute("SELECT venue_id,name FROM Venue ORDER BY name"); venues=cur.fetchall()
    cur.execute("SELECT stage_id,stage_info FROM TournamentStage"); stages=cur.fetchall()
    cur.execute("SELECT team_id,name FROM Team ORDER BY name"); teams=cur.fetchall()
    conn.close()
    return render_template('admin_match_form.html',
                           match=match, venues=venues, stages=stages, teams=teams, action='Edit')

@app.route('/admin/matches/delete/<int:id>')
def admin_matches_delete(id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM MatchTeam WHERE match_id=%s", (id,))
    cur.execute("DELETE FROM Matches    WHERE match_id=%s", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin_matches'))



# ------------ GROUPS MANAGEMENT ------------

@app.route('/admin/groups')
def admin_groups():
    conn=get_db_connection(); cur=conn.cursor(dictionary=True)
    cur.execute("""SELECT gt.group_id,gn.group_name,
                          t.team_id, t.name AS team_name,
                          gt.matches_played,gt.qualified
                   FROM GroupTeam gt
                   JOIN GroupsName gn ON gt.group_id=gn.group_id
                   JOIN Team t ON gt.team_id=t.team_id
                   ORDER BY gn.group_name, t.name""")
    entries = cur.fetchall(); conn.close()
    # group them
    groups = {}
    for e in entries:
      groups.setdefault(e['group_name'], []).append(e)
    return render_template('admin_groups.html', groups=groups)

@app.route('/admin/groups/add', methods=['GET','POST'])
def admin_groups_add():
    conn=get_db_connection(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        cur.execute("""INSERT INTO GroupTeam
                       (group_id,team_id,matches_played,qualified)
                       VALUES(%s,%s,%s,%s)""",
                    (request.form['group_id'],
                     request.form['team_id'],
                     request.form['matches_played'],
                     bool(request.form.get('qualified'))))
        conn.commit(); conn.close()
        return redirect(url_for('admin_groups'))
    cur.execute("SELECT group_id,group_name FROM GroupsName"); groups=cur.fetchall()
    cur.execute("SELECT team_id,name FROM Team ORDER BY name"); teams=cur.fetchall()
    conn.close()
    return render_template('admin_group_form.html',
                           groups=groups,teams=teams)

@app.route('/admin/groups/edit/<int:group_id>/<int:team_id>', methods=['GET','POST'])
def admin_groups_edit(group_id, team_id):
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        cur.execute("""
            UPDATE GroupTeam
               SET group_id=%s, team_id=%s, matches_played=%s, qualified=%s
             WHERE group_id=%s AND team_id=%s
        """, (
            request.form['group_id'],
            request.form['team_id'],
            request.form['matches_played'],
            bool(request.form.get('qualified')),
            group_id, team_id
        ))
        conn.commit(); conn.close()
        return redirect(url_for('admin_groups'))
    # GET: load entry + dropdowns
    cur.execute("SELECT * FROM GroupTeam WHERE group_id=%s AND team_id=%s", (group_id, team_id))
    entry = cur.fetchone()
    cur.execute("SELECT group_id,group_name FROM GroupsName ORDER BY group_name"); groups=cur.fetchall()
    cur.execute("SELECT team_id,name FROM Team ORDER BY name"); teams=cur.fetchall()
    conn.close()
    return render_template('admin_group_form.html',
                           entry=entry, groups=groups, teams=teams, action='Edit')

@app.route('/admin/groups/delete/<int:group_id>/<int:team_id>')
def admin_groups_delete(group_id, team_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM GroupTeam WHERE group_id=%s AND team_id=%s", (group_id, team_id))
    conn.commit(); conn.close()
    return redirect(url_for('admin_groups'))


@app.route("/test_db")
def test_db():
    try:
        conn = get_db_connection()
        if conn.is_connected():
            version = conn.get_server_info()
            conn.close()
            return jsonify({"status": "OK", "mysql_version": version})
        else:
            return jsonify({"status": "FAILED", "error": "Connection not open"})
    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)})


if __name__=='__main__':
    app.run(debug=True)
