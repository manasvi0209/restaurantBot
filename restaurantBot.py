import gradio as gr
import requests
from fastapi import FastAPI
from pydantic import BaseModel
import threading
import uvicorn

# ==============================
# RESTAURANT BOT LOGIC (unchanged)
# ==============================

# Menu with prices
menu = {
    "pizza": 150,
    "burger": 80,
    "pasta": 120,
    "coffee": 50,
    "sandwich": 60
}

# Orders dictionary to track user’s current orders
orders = {}
waiting_for_address = False   # <-- global state
delivery_mode = False         # <-- track if delivery is chosen

def restaurant_bot(user_input):
    global waiting_for_address, delivery_mode

    user_input = user_input.lower().strip()
    response = ""

    # 👋 Greetings
    greetings = ["hello", "hi", "hey", "good morning", "good evening","hii"]
    if user_input in greetings:
        return "👋 Hello! Welcome to our restaurant. How may I help you today?\n(Type 'menu' to see available items.)"

    # If waiting for address
    if waiting_for_address:
        delivery_address = user_input
        total = sum(menu[item] * qty for item, qty in orders.items())
        response = "✅ Your final order:\n"
        for item, qty in orders.items():
            response += f"- {item.title()} x {qty} = ₹{menu[item] * qty}\n"
        response += f"\n💰 Total: ₹{total}\n"
        response += f"📍 Delivery Address: {delivery_address}\n"
        response += "\n🙏 Thank you for your order! It will be delivered soon."
        orders.clear()
        waiting_for_address = False
        delivery_mode = False
        return response

    # Add multiple items with quantities
    words = user_input.split()
    i = 0
    added = []

    while i < len(words):
        if words[i].isdigit() and i + 1 < len(words):
            qty = int(words[i])
            item_name = words[i + 1].lower()
            
            # check against menu (supporting partial matches)
            for item in menu.keys():
                if item.startswith(item_name.rstrip("s")):  # handle plurals
                    orders[item] = orders.get(item, 0) + qty
                    added.append(f"{qty} {item}(s)")
                    break
            i += 2
        else:
            i += 1

    if added:
        response = "✅ Added " + " and ".join(added) + " to your order."

    # Cancel items
    for item in menu.keys():
        if f"cancel {item}" in user_input:
            if item in orders and orders[item] > 0:
                orders[item] -= 1
                if orders[item] == 0:
                    del orders[item]
                response = f"❌ Removed {item} from your order."
            else:
                response = f"⚠️ You don't have {item} in your order."
            break

    # Show menu
    if "menu" in user_input:
        response = "📋 Here’s our menu:\n"
        for food, price in menu.items():
            response += f"- {food.capitalize()} : ₹{price}\n"

    # Show order
    elif "order" in user_input or "cart" in user_input:
        if orders:
            total = sum(menu[item] * qty for item, qty in orders.items())
            response = "🛒 Your current order:\n"
            for item, qty in orders.items():
                response += f"- {item.capitalize()} x{qty} = ₹{menu[item] * qty}\n"
            response += f"\n💰 Total = ₹{total}"
        else:
            response = "🛒 Your cart is empty."

    # Finalize with delivery
    delivery_keywords = ["delivery", "home delivery", "address", "destination"]
    if "finalize" in user_input and any(keyword in user_input for keyword in delivery_keywords):
        if not orders:
            return "🛒 You don’t have any items in your order."
        waiting_for_address = True
        delivery_mode = True
        return "🚚 Please provide your delivery address to complete the order."

    # Finalize with parcel
    if "finalize" in user_input and "order" in user_input:
        if not orders:
            return "🛒 You don’t have any items in your order."
        total = sum(menu[item] * qty for item, qty in orders.items())
        response = "✅ Your final order:\n"
        for item, qty in orders.items():
            response += f"- {item.title()} x {qty} = ₹{menu[item] * qty}\n"
        response += f"\n💰 Total: ₹{total}\n"
        response += "\n📦 Your order will be packed for takeaway. Thank you!"
        orders.clear()
        return response

    # Normal finalize
    if "finalize" in user_input or "bill" in user_input or "checkout" in user_input:
        if not orders:
            return "🛒 You don’t have any items in your order."
        total = sum(menu[item] * qty for item, qty in orders.items())
        response = "✅ Your final order:\n"
        for item, qty in orders.items():
            response += f"- {item.title()} x {qty} = ₹{menu[item] * qty}\n"
        response += f"\n💰 Total: ₹{total}\n🙏 Thank you for your order!"
        orders.clear()
        return response

    # Help
    elif "help" in user_input:
        response = (
            "💡 You can:\n"
            "- Type an item name to add it (e.g., 'pizza')\n"
            "- Type 'cancel <item>' to remove (e.g., 'cancel burger')\n"
            "- Type 'menu' to see the menu\n"
            "- Type 'order' to view your cart\n"
            "- Type 'bill' to finalize"
        )

    if not response:
        response = "Sorry, I didn’t understand that. Type 'menu' to see options."

    return response


# ==============================
# FASTAPI BACKEND
# ==============================
app = FastAPI()

class UserInput(BaseModel):
    message: str

@app.post("/chat")
def chat(user: UserInput):
    reply = restaurant_bot(user.message)
    return {"reply": reply}


# ==============================
# GRADIO FRONTEND (calls API)
# ==============================
API_URL = "http://localhost:8000/chat"

def respond(message, chat_history):
    response = requests.post(API_URL, json={"message": message})
    bot_reply = response.json()["reply"]
    chat_history.append((message, bot_reply))
    return "", chat_history

def start_gradio():
    with gr.Blocks() as demo:
        gr.Markdown("## 🍴 Restaurant Ordering Bot (API-Powered)")
        chatbot = gr.Chatbot(height=300)
        msg = gr.Textbox(label="Type your request here")
        clear = gr.Button("Clear Chat")

        msg.submit(respond, [msg, chatbot], [msg, chatbot])
        clear.click(lambda: None, None, chatbot, queue=False)

    demo.launch(server_port=7860, share=True)

# ==============================
# RUN BOTH API + GRADIO
# ==============================
def run_all():
    # Run FastAPI in separate thread
    def run_api():
        uvicorn.run(app, host="0.0.0.0", port=8000)
    threading.Thread(target=run_api, daemon=True).start()

    # Run Gradio UI
    start_gradio()

if __name__ == "__main__":
    run_all()
