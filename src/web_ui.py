"""Dependency-free local web dashboard for the drone patrol prototype."""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.agent import AnalystAgent
from src.indexer import Indexer
from src.simulator import load_scenario
from main import DEFAULT_ALERT_LOG, _database_path, run_pipeline


_DASHBOARD = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drone Security | Patrol Console</title>
<style>
:root{color-scheme:light;--bg:#f4f3ef;--panel:#fff;--panel2:#f7f6f2;--line:#e4e1d9;--text:#202b31;--muted:#77827f;--cyan:#157d72;--blue:#476d96;--red:#b8453d;--amber:#ab701f;--green:#39865d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 "Segoe UI",Inter,system-ui,sans-serif}
.wrap{max-width:1500px;margin:auto;padding:26px 34px 56px}.top{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 23px;margin-bottom:23px;border-bottom:1px solid #dcd9d0}.brand{display:flex;align-items:center;gap:14px}.logo{width:44px;height:44px;border-radius:12px;background:#173c3b;display:grid;place-items:center;color:#d4ede4;font-size:23px;font-weight:900}.eyebrow{color:var(--cyan);font-size:10px;letter-spacing:2.1px;text-transform:uppercase;font-weight:800}h1{font-size:27px;margin:1px 0 0;letter-spacing:-.8px;font-weight:680}.sub{color:var(--muted);font-size:12px}.actions{display:flex;gap:9px;align-items:center}button,select,input{font:inherit}button{border:1px solid var(--line);border-radius:7px;padding:9px 14px;color:var(--text);background:var(--panel);cursor:pointer;transition:background .15s,border-color .15s}button:hover{border-color:var(--cyan);background:#f1f8f5}button.primary{background:#173c3b;border-color:#173c3b;color:white;font-weight:700}.status{border:1px solid var(--line);border-radius:7px;padding:8px 11px;color:var(--muted);font-size:11px;background:white}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:7px}.status.running .dot{background:var(--amber);box-shadow:0 0 8px #d7ad72;animation:pulse 1s infinite}@keyframes pulse{50%{opacity:.35}}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:17px}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 7px rgba(32,43,49,.025)}.card{padding:16px 18px;border-top:3px solid #c8dcd4}.card:nth-child(3){border-top-color:#e4c9a7}.card-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.7px;font-weight:700}.card-value{font-size:29px;line-height:1.2;font-weight:720;margin:8px 0 4px;letter-spacing:-.8px}.card-foot{font-size:11px;color:var(--muted)}.layout{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,.82fr);gap:16px;align-items:start}.panel{padding:18px 19px;margin-bottom:15px}.panel-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}.panel h2{font-size:15px;margin:0;font-weight:700;letter-spacing:-.2px}.tag{font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:4px 7px;background:#faf9f6}.progress{height:4px;border-radius:5px;background:#eeede8;overflow:hidden;margin:10px 0}.progress>i{display:block;height:100%;width:0;background:var(--cyan);transition:width .25s}.log{height:150px;overflow:auto;background:#f8f8f5;border:1px solid #eeece5;border-radius:7px;padding:9px 12px;font:11px/1.7 Consolas,monospace}.logline{white-space:pre-wrap;color:#55615f}.logline.alert-high{color:var(--red)}.logline.alert-medium{color:var(--amber)}.logline.alert-low{color:var(--blue)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}input,select{min-width:0;background:#fff;border:1px solid #deddd6;border-radius:6px;color:var(--text);padding:9px 10px}input{flex:1}select{max-width:170px}input:focus,select:focus{outline:2px solid #b8d8ce;border-color:var(--cyan)}.tablewrap{overflow:auto;max-height:430px}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:#78817d;font-size:10px;letter-spacing:.7px;font-weight:750;position:sticky;top:0;background:#f7f6f2;padding:10px 8px;border-bottom:1px solid var(--line)}td{padding:10px 8px;border-bottom:1px solid #efeee9;vertical-align:top}tbody tr:hover{background:#fbfbf8}td.desc{min-width:230px;color:#596561}.zone{color:var(--cyan);white-space:nowrap;font-weight:650}.empty{color:var(--muted);padding:20px;text-align:center}.alertlist{display:grid;gap:8px;max-height:320px;overflow:auto}.alert{padding:10px 11px;border:1px solid #eeece5;border-left:3px solid var(--red);border-radius:6px;background:#fff}.alert.MEDIUM{border-left-color:var(--amber)}.alert.LOW{border-left-color:var(--blue)}.alert-top{display:flex;justify-content:space-between;font-size:10px;font-weight:800}.alert p{font-size:12px;margin:4px 0 0;color:#596561}.HIGH{color:var(--red)}.MEDIUM{color:var(--amber)}.LOW{color:var(--blue)}
.chat{display:flex;gap:8px}.chat input{flex:1}.answer{margin-top:11px;padding:12px;border:1px solid #eeece5;border-radius:7px;background:#f8f8f5;white-space:pre-wrap;color:#4d5b57;font-size:12px;min-height:44px}.summary{color:#596561;font-size:12px}.hint{font-size:10px;color:var(--muted);margin-top:9px}
@media(max-width:950px){.layout{grid-template-columns:1fr}.wrap{padding:20px 16px}.cards{grid-template-columns:repeat(2,1fr)}}@media(max-width:550px){.top{align-items:flex-start;flex-direction:column}.actions{width:100%;flex-wrap:wrap}.cards{gap:9px}.card{padding:13px}.card-value{font-size:23px}}
</style></head>
<body><main class="wrap">
<header class="top"><div class="brand"><div class="logo">◈</div><div><div class="eyebrow">Northstar · Property security</div><h1>Patrol overview</h1><div class="sub">Daily operations · Docked drone system</div></div></div>
<div class="actions"><span id="status" class="status"><i class="dot"></i><span id="statusText">Connecting</span></span><select id="speed" title="Replay multiplier"><option value="0">Instant replay</option><option value="60">Replay ×60</option><option value="600">Replay ×600</option></select><button id="runBtn" class="primary">▶ Start patrol</button><button id="refreshBtn">↻ Refresh</button></div></header>
<section class="cards"><div class="card"><div class="card-label">Frames indexed</div><div class="card-value" id="frames">—</div><div class="card-foot">from today's scenario</div></div><div class="card"><div class="card-label">Detected objects</div><div class="card-value" id="objects">—</div><div class="card-foot">indexed observations</div></div><div class="card"><div class="card-label">Alerts raised</div><div class="card-value" id="alertCount">—</div><div class="card-foot">high / medium / low</div></div><div class="card"><div class="card-label">Zones covered</div><div class="card-value" id="zones">—</div><div class="card-foot">property patrol route</div></div></section>
<div class="layout"><section>
<div class="panel"><div class="panel-head"><h2>Patrol activity</h2><span class="tag" id="runProgress">Ready</span></div><div class="progress"><i id="progressBar"></i></div><div id="runLog" class="log"><div class="logline">System ready · Start a patrol to populate today's activity.</div></div></div>
<div class="panel"><div class="panel-head"><h2>Event register</h2><span class="tag" id="resultCount">All frames</span></div><form id="searchForm" class="filters"><select id="searchMode"><option value="all">All events</option><option value="object">Object</option><option value="text">Description text</option><option value="time">Time range</option></select><input id="searchInput" placeholder="Search events, zones, or time"><button class="primary" type="submit">Apply filter</button></form><div class="tablewrap"><table><thead><tr><th>TIME</th><th>ZONE</th><th>DETECTIONS</th><th>FRAME DESCRIPTION</th></tr></thead><tbody id="framesBody"></tbody></table></div></div>
</section><aside>
<div class="panel"><div class="panel-head"><h2>Alert inbox</h2><select id="severityFilter"><option value="">All severities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></div><div id="alerts" class="alertlist"></div></div>
<div class="panel"><div class="panel-head"><h2>Ask the analyst</h2><span class="tag">Local search</span></div><form id="askForm" class="chat"><input id="question" placeholder="Ask about today's patrol…" required><button class="primary" type="submit">Ask</button></form><div id="answer" class="answer">Ask about objects, vehicle entries, alerts, or a time range.</div><div class="hint">Try “How many times did the F150 enter today?” or “Any alerts at night?”</div></div>
<div class="panel"><div class="panel-head"><h2>Shift summary</h2></div><div id="summary" class="summary">Run the patrol to build today's recap.</div></div>
</aside></div></main>
<script>
const $=id=>document.getElementById(id);let busy=false;
function text(node,value){node.textContent=value}
async function request(path,options={}){const response=await fetch(path,{headers:{"Content-Type":"application/json"},...options});const body=await response.json();if(!response.ok)throw new Error(body.error||"Request failed");return body}
function setStatus(state,error){const el=$("status");el.classList.toggle("running",state==="running");text($("statusText"),error?"Error":state==="running"?"Patrol running":state==="completed"?"Patrol complete":state==="failed"?"Patrol failed":"Ready");}
function drawFrames(frames){const body=$("framesBody");body.replaceChildren();text($("resultCount"),`${frames.length} frame${frames.length===1?"":"s"}`);if(!frames.length){const row=document.createElement("tr"),cell=document.createElement("td");cell.colSpan=4;cell.className="empty";cell.textContent="No matching frames. Run the patrol or change your search.";row.append(cell);body.append(row);return}for(const frame of frames){const row=document.createElement("tr"),time=document.createElement("td"),zone=document.createElement("td"),objects=document.createElement("td"),desc=document.createElement("td");time.textContent=frame.ts.slice(11,16);zone.textContent=frame.zone;zone.className="zone";objects.textContent=[...new Set((frame.objects||[]).map(o=>o.label))].join(", ")||"—";desc.textContent=frame.description;desc.className="desc";for(const cell of [time,zone,objects,desc])row.append(cell);body.append(row)}}
function drawAlerts(alerts){const box=$("alerts");box.replaceChildren();if(!alerts.length){const div=document.createElement("div");div.className="empty";div.textContent="No alerts to show.";box.append(div);return}for(const item of alerts){const card=document.createElement("div"),top=document.createElement("div"),severity=document.createElement("span"),time=document.createElement("span"),message=document.createElement("p");card.className=`alert ${item.severity}`;top.className="alert-top";severity.className=item.severity;severity.textContent=`${item.severity} · ${item.rule.replaceAll("_"," ")}`;time.textContent=item.ts.slice(11,16);message.textContent=item.message;top.append(severity,time);card.append(top,message);box.append(card)}}
async function refresh(){try{const data=await request("/api/state");text($("frames"),data.frames);text($("objects"),data.objects);text($("alertCount"),data.alert_count);text($("zones"),data.zones);setStatus(data.run.state,data.run.error);text($("runProgress"),data.run.state==="running"?`${data.run.processed}/${data.run.total} frames`:data.run.state==="failed"?"Run failed":data.run.state==="completed"?"Complete":"Ready");$("progressBar").style.width=data.run.total?`${Math.round(data.run.processed/data.run.total*100)}%`:"0%";drawAlerts(data.alerts.filter(a=>!$("severityFilter").value||a.severity===$("severityFilter").value));if(!$("searchInput").value)drawFrames(data.frames_list);if(data.run.events?.length){const log=$("runLog");log.replaceChildren();for(const line of data.run.events.slice(-80)){const entry=document.createElement("div");entry.className="logline"+(line.includes("[HIGH]")?" alert-high":line.includes("[MEDIUM]")?" alert-medium":line.includes("[LOW]")?" alert-low":"");entry.textContent=line;log.append(entry)}log.scrollTop=log.scrollHeight}text($("summary"),data.summary||"Run the patrol to build today's recap.");}catch(error){setStatus("failed",true);text($("statusText"),error.message)}}
async function search(){const mode=$("searchMode").value,query=$("searchInput").value.trim();if(mode!=="all"&&!query){text($("searchInput").placeholder, "");$("searchInput").focus();return}try{const result=await request("/api/search",{method:"POST",body:JSON.stringify({mode,query})});drawFrames(result.frames)}catch(error){text($("resultCount"),error.message)}}
$("runBtn").addEventListener("click",async()=>{if(busy)return;busy=true;$("runBtn").disabled=true;try{await request("/api/run",{method:"POST",body:JSON.stringify({speed:Number($("speed").value)})});await refresh()}catch(error){text($("runProgress"),error.message)}finally{busy=false;$("runBtn").disabled=false}});
$("refreshBtn").addEventListener("click",refresh);$("severityFilter").addEventListener("change",refresh);$("searchForm").addEventListener("submit",event=>{event.preventDefault();search()});$("searchMode").addEventListener("change",()=>{$("searchInput").placeholder=$("searchMode").value==="time"?"00:00-01:00":$("searchMode").value==="object"?"truck, person, red, Ford F150":"Search frame descriptions"});$("askForm").addEventListener("submit",async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;text($("answer"),"Analyst is searching the patrol index…");try{const result=await request("/api/ask",{method:"POST",body:JSON.stringify({question:$("question").value})});text($("answer"),result.answer)}catch(error){text($("answer"),error.message)}finally{button.disabled=false}});
refresh();setInterval(()=>{if(!busy)refresh()},2000);
</script></body></html>"""


class Dashboard:
    """Own dashboard state while keeping SQLite access on the serving thread."""

    def __init__(self, database_path: str | Path, alert_log_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.alert_log_path = Path(alert_log_path)
        self.indexer = Indexer(self.database_path, check_same_thread=False)
        self.agent = AnalystAgent(self.indexer)
        self.lock = threading.Lock()
        self.run_state: dict[str, Any] = {
            "state": "idle",
            "processed": 0,
            "total": len(load_scenario()),
            "events": [],
            "error": None,
        }

    def start_run(self, speed: float) -> None:
        if speed < 0:
            raise ValueError("speed must be non-negative")
        with self.lock:
            if self.run_state["state"] == "running":
                raise RuntimeError("A patrol run is already in progress")
            self.run_state = {
                "state": "running",
                "processed": 0,
                "total": len(load_scenario()),
                "events": [],
                "error": None,
            }
        worker = threading.Thread(target=self._run_pipeline, args=(speed,), daemon=True)
        worker.start()

    def _run_pipeline(self, speed: float) -> None:
        try:
            worker_indexer = Indexer(self.database_path)

            def log_event(message: str) -> None:
                with self.lock:
                    self.run_state["events"].append(message)

            def progress(current: int, total: int) -> None:
                with self.lock:
                    self.run_state["processed"] = current
                    self.run_state["total"] = total

            try:
                run_pipeline(
                    worker_indexer,
                    speed=speed,
                    output=log_event,
                    alert_log_path=self.alert_log_path,
                    on_frame=progress,
                )
            finally:
                worker_indexer.close()
            with self.lock:
                self.run_state["state"] = "completed"
        except Exception as error:
            with self.lock:
                self.run_state["state"] = "failed"
                self.run_state["error"] = str(error)

    def state(self) -> dict[str, Any]:
        connection = self.indexer.connection
        frames = int(connection.execute("SELECT COUNT(*) FROM frames").fetchone()[0])
        objects = int(connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
        zones = int(
            connection.execute("SELECT COUNT(DISTINCT zone) FROM frames").fetchone()[0]
        )
        frame_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM frames ORDER BY ts DESC LIMIT 50"
            ).fetchall()
        ]
        frames_list = self.indexer._frame_results(frame_ids)
        frames_list.reverse()
        alerts = self.indexer.list_alerts()
        with self.lock:
            run = dict(self.run_state)
            run["events"] = list(self.run_state["events"])
        if run["state"] == "completed" and frames < run["total"]:
            return self.state()
        return {
            "frames": frames,
            "objects": objects,
            "zones": zones,
            "alerts": alerts,
            "alert_count": len(alerts),
            "frames_list": frames_list,
            "summary": self.agent.summarize_day(),
            "run": run,
        }

    def close(self) -> None:
        self.indexer.close()


def create_server(host: str = "127.0.0.1", port: int = 8765) -> HTTPServer:
    """Create the local dashboard server."""
    database_path = _database_path()
    dashboard = Dashboard(database_path, DEFAULT_ALERT_LOG)

    class DashboardHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16_384:
                raise ValueError("Request body is too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            return payload

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                body = _DASHBOARD.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/healthz":
                self._send_json({"status": "ok"})
            elif path == "/api/state":
                self._send_json(dashboard.state())
            else:
                self._send_json({"error": "Not found"}, 404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = self._read_json()
                if path == "/api/run":
                    dashboard.start_run(float(payload.get("speed", 0)))
                    self._send_json({"started": True}, 202)
                elif path == "/api/ask":
                    question = str(payload.get("question", "")).strip()
                    if not question:
                        raise ValueError("Enter a question")
                    self._send_json({"answer": dashboard.agent.ask(question)})
                elif path == "/api/search":
                    mode = str(payload.get("mode", "all"))
                    query = str(payload.get("query", "")).strip()
                    if mode == "all":
                        frames = dashboard.indexer.query_by_object()
                        if not query:
                            rows = dashboard.indexer.connection.execute(
                                "SELECT id FROM frames ORDER BY ts DESC LIMIT 50"
                            ).fetchall()
                            frames = dashboard.indexer._frame_results(
                                [row["id"] for row in rows]
                            )
                            frames.reverse()
                    elif mode == "time":
                        parts = query.split("-", maxsplit=1)
                        if len(parts) != 2:
                            raise ValueError("Use a time range such as 00:00-01:00")
                        frames = dashboard.indexer.query_by_time(*parts)
                    elif mode == "object":
                        known_types = {
                            "person", "vehicle", "animal", "other",
                            "truck", "van", "car", "sedan", "pickup",
                        }
                        if query.lower() in known_types:
                            frames = dashboard.indexer.query_by_object(type=query)
                        else:
                            frames = dashboard.indexer.query_by_object(make=query)
                            if not frames:
                                frames = dashboard.indexer.query_by_object(color=query)
                    elif mode == "text":
                        frames = dashboard.indexer.search_text(query)
                    else:
                        raise ValueError("Unknown search mode")
                    self._send_json({"frames": frames})
                else:
                    self._send_json({"error": "Not found"}, 404)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, 400)
            except RuntimeError as error:
                self._send_json({"error": str(error)}, 409)
            except Exception as error:
                self._send_json({"error": f"Dashboard request failed: {error}"}, 500)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((host, port), DashboardHandler)
    server.dashboard = dashboard  # type: ignore[attr-defined]
    return server


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the dashboard until interrupted."""
    server = create_server(host, port)
    url_host = "127.0.0.1" if host == "0.0.0.0" else host
    dashboard_url = f"http://{url_host}:{server.server_port}"
    print(f"Drone Security dashboard: {dashboard_url}")
    print("Press Ctrl+C to stop.")
    if host in {"127.0.0.1", "localhost"}:
        threading.Timer(0.8, webbrowser.open, args=(dashboard_url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.dashboard.close()  # type: ignore[attr-defined]
        server.server_close()
