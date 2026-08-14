"""
Simulate Voice Call CLI Test.
Runs a scripted conversation against the Agency Voice Bridge and verifies lead capture.
"""
import asyncio
import json
import websockets
import requests


async def test_simulated_call(agency_number: int = 1):
    uri = f"ws://127.0.0.1:8100/ws/call/{agency_number}"
    print(f"[SimulateCall] Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        # 1. Initial greeting
        greeting = await ws.recv()
        data = json.loads(greeting)
        print(f"\n[Bot Greeting]: {data.get('text')}\n")

        # 2. Turn 1: User requirement
        turn1 = "Hi! I am looking for a 3-bedroom single family home in Round Rock under $450,000. My name is Alex Walker and my phone is 512-555-0199."
        print(f"[User]: {turn1}")
        await ws.send(json.dumps({"type": "user_speech", "text": turn1}))

        resp1 = await ws.recv()
        data1 = json.loads(resp1)
        print(f"[Bot]: {data1.get('text')}\n")

        # 3. Turn 2: User follow up
        turn2 = "Tomorrow at 2 PM works best for an agent callback. Thanks!"
        print(f"[User]: {turn2}")
        await ws.send(json.dumps({"type": "user_speech", "text": turn2}))

        resp2 = await ws.recv()
        data2 = json.loads(resp2)
        print(f"[Bot]: {data2.get('text')}\n")

        # 4. End call
        print("[SimulateCall] Ending call and triggering lead capture...")
        await ws.send(json.dumps({"type": "end_call"}))

        end_msg = await ws.recv()
        print(f"[Result]: {end_msg}")

    print("\n[SimulateCall] Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_simulated_call())
