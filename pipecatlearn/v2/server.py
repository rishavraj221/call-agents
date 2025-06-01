import argparse, json, uvicorn, os
from urllib.parse import urlencode

from pipecatlearn.v2.bot import run_bot
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from pydantic import BaseModel
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv(override=True)

app = FastAPI()

xml_path = f"/Users/rishavraj/Downloads/Codes/agentic-ai/pipecatlearn/v2/templates/streams.xml"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
DEFAULT_TO_NUMBER = os.getenv("DEFAULT_TO_NUMBER")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Pydantic model for outbound call request
class OutboundCallRequest(BaseModel):
    to_number: str
    from_number: str = None # Optional, will use default if not provided

@app.post("/")
async def start_call():
    """Handle incoming calls - returns TwiML for media streams"""
    print("POST TwiML - Incoming Call")
    return HTMLResponse(content=open(xml_path).read(), media_type="application/xml")

@app.get("/outbound")
async def initiate_outbound_call(
    req: Request, 
    to_number: str = DEFAULT_TO_NUMBER, 
    from_number: str = None
):
    """Initiate an outbound call to the specified number"""
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise HTTPException(status_code=500, detail="Twilio credentials not configured")
        
        client = Client(username=TWILIO_ACCOUNT_SID, password=TWILIO_AUTH_TOKEN)

        # Use provided from_number or default from environment
        from_number = from_number or TWILIO_PHONE_NUMBER
        if not from_number:
            raise HTTPException(status_code=400, detail="From number not provided and no default configured")

        # Get the base URL for webhooks
        base_url = f"{req.url.scheme}://{req.url.netloc}"

        # Create the call
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            url=f"{base_url}/outbound-twiml", # This will handle the TwiML for outbound calls
            method="POST"
        )

        print(f"Outbound call initiated: {call.sid}")
        print(f"Using webhook URL: {base_url}/outbound-twiml")
        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "to": to_number,
            "from": from_number,
            "webhook_url": f"{base_url}/outbound-twiml"
        }

    except Exception as e:
        print(f"Error initiating outbound call: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")
    
@app.post("/outbound-twiml")
async def outbound_twiml():
    """Handle outbound call connection - returns TwiML for media streams"""
    print("POST TwiML - Outbound Call Connected")
    return HTMLResponse(content=open(xml_path).read(), media_type="application/xml")

@app.get("/call-status/{call_sid}")
async def get_call_status(call_sid: str):
    """Get the status of a specific call"""
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise HTTPException(status_code=500, detail="Twilio credentials not configured")
        
        client = Client(username=TWILIO_ACCOUNT_SID, password=TWILIO_AUTH_TOKEN)
        call = client.calls(call_sid).fetch()

        return {
            "call_sid": call.sid,
            "status": call.status,
            "direction": call.direction,
            "to": call.to,
            "duration": call.duration,
            "start_time": call.start_time,
            "end_time": call.end_time
        }
    except Exception as e:
        print(f"Error fetching call status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch call status: {str(e)}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    start_data = websocket.iter_text()
    await start_data.__anext__()
    call_data = json.loads(await start_data.__anext__())
    print(call_data, flush=True)
    stream_sid = call_data["start"]["streamSid"]
    call_sid = call_data["start"]["callSid"]
    print("WebSocket connection accepted")
    await run_bot(websocket, stream_sid, call_sid, app.state.testing)

def main():
    # parser = argparse.ArgumentParser(description="Pipecat Twilio Chatbot Server")
    # parser.add_argument(
    #     "-t", "--test", action="store_true", default=False, help="set the server in testing mode"
    # )
    # args, _ = parser.parse_known_args()

    # app.state.testing = args.test

    app.state.testing = True

    uvicorn.run(app, host="0.0.0.0", port=8765)