import os
import sys
import asyncio

from uvicorn import Config, Server

if sys.platform.startswith("win"):
    from asyncio.windows_events import ProactorEventLoop
    asyncio.set_event_loop(asyncio.ProactorEventLoop())


print("🔥 start.py is executing...")

if __name__ == "__main__":
    try:
        if sys.platform.startswith("win"):
            class ProactorServer(Server):
                def run(self, sockets=None):
                    loop = ProactorEventLoop()
                    asyncio.set_event_loop(loop)
                    asyncio.run(self.serve(sockets=sockets))
                    
            server_class = ProactorServer
        else:
            # On Linux/macOS just use normal Server
            server_class = Server
                
        port = int(os.environ.get("PORT", 8010))
        print(f"🚀 Starting server on port {port}...")
        config = Config(app="app.main:app", host="0.0.0.0", port=port, reload=False)
        server = server_class(config=config)
        server.run()
        print('✅ Server Started Successfully.')

    except Exception as e:
        print(f"❌ Failed to start: {e}")
