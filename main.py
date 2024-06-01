from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_help
import basic_help

app = FastAPI()

inprogress_orders = {}


@app.post("/")
async def handle_request(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()

    # Extract the necessary information from the payload
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']
    session_id = basic_help.extract_session_id(output_contexts[0]["name"])

    intent_handler_dict = {
        'add.order': add_to_order,
        'order.remove': remove_from_order,
        'order.complete': complete_order,
        'track.order.id': track_order
    }

    if intent in intent_handler_dict:
        return await intent_handler_dict[intent](parameters, session_id)
    else:
        return JSONResponse(content={
            "fulfillmentText": "Sorry, I didn't understand that intent."
        })


def save_to_db(order: dict):
    next_order_id = db_help.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for food_item, quantity in order.items():
        rcode = db_help.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_help.insert_order_tracking(next_order_id, "in progress")

    return next_order_id


async def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "Apologies, but I'm unable to find your order. Could you please place it again?type 1 for new order"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)
        if order_id == -1:
            fulfillment_text = "I'm sorry, there was an issue with our system processing your order. Can you place it once more?type 1 for new order"
        else:
            order_total = db_help.get_total_order_price(order_id)
            fulfillment_text = (
                f"Awesome. We have placed your order. "
                f"Here is your order id #{order_id}. "
                f"Your order total is {
                    order_total} which you can pay at the time of delivery!"
            )

        del inprogress_orders[session_id]

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


async def add_to_order(parameters: dict, session_id: str):
    food_items = parameters["food_item"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry, I didn't catch that. Please provide the food items and quantities clearly."
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_orders:
            current_food_dict = inprogress_orders[session_id]
            current_food_dict.update(new_food_dict)
        else:
            inprogress_orders[session_id] = new_food_dict

        order_str = basic_help.get_str_from_food_dict(
            inprogress_orders[session_id])
        fulfillment_text = f"Here's your order: {
            order_str}. Is your order confirmed?Type Yes to confirm your order.If you want to Add more  type Add with food & the quantity or to remove type remove with the food & the quantity"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


async def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "Apologies, but I'm unable to find your order. Could you please place it again?"
        })

    food_items = parameters["food_item"]
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    fulfillment_text = ""
    if len(removed_items) > 0:
        fulfillment_text = f"Removed {
            ', '.join(removed_items)} from your order!"

    if len(no_such_items) > 0:
        fulfillment_text += f" Your current order does not have {
            ', '.join(no_such_items)}."

    if len(current_order.keys()) == 0:
        fulfillment_text += " Your order is empty!"
    else:
        order_str = basic_help.get_str_from_food_dict(current_order)
        fulfillment_text += f" Here are the remaining items in your order: {
            order_str}. please type Yes to confirm your order"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


async def track_order(parameters: dict, session_id: str):
    order_id = int(parameters['order_id'])
    order_status = db_help.get_order_status(order_id)
    if order_status:
        fulfillment_text = f"Your order with ID {
            order_id} is currently {order_status}."
    else:
        fulfillment_text = f"I couldn't find any order with the Id {order_id}"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
