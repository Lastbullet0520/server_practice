from flask import Flask, request, jsonify, render_template
import os
from pymongo import MongoClient
import cv2
from ultralytics import YOLO
import torchvision.transforms as transforms
from PIL import Image
import spoonacular
import pandas

app = Flask(__name__)
client = MongoClient("localhost", 27017)
db = client.dbintel

configuration = spoonacular.Configuration(
    host="https://api.spoonacular.com"
)
configuration.api_key['apiKeyScheme'] = "4adcee865a5b4cde8580e088bffdd841"

model = YOLO("yolov8n.pt")

# 이미지 저장 경로 설정
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/findfoodlist", methods=["GET"])  # 식재료와 레시피 출력할 갯수 넣으면 JSON 받을 수 있다
def findfoodlist():
    ingredients = str(request.args.get("ingredients"))
    print(ingredients)

    with spoonacular.ApiClient(configuration) as api_client:
        api_instance = spoonacular.RecipesApi(api_client)
        limit_license = True
        ranking = 1
        ignore_pantry = False

        try:
            api_response = api_instance.search_recipes_by_ingredients(
                ingredients=ingredients,
                number=2,
                limit_license=limit_license,
                ranking=ranking,
                ignore_pantry=ignore_pantry
            )
            response_dict = [result.to_dict() for result in api_response]
            return jsonify(response_dict)
        except Exception as e:
            print("Exception when calling RecipesApi->search_recipes_by_ingredients: %s\n" % e)
            return jsonify({"error": str(e)}), 500


# @app.route("/recipeout", methods=["GET"])
# def recipeout():
#     with spoonacular.ApiClient(configuration) as api_client:
#         # Create an instance of the API class
#         api_instance = spoonacular.RecipesApi(api_client)
#         ids = int(request.args.get("id"))  # int | The item's id.
#         include_nutrition = True  # bool | Include nutrition data in the recipe information. Nutrition data is per serving. If you want the nutrition data for the entire recipe, just multiply by the number of servings. (optional) (default to False)
#
#         try:
#             # Get Recipe Information
#             api_response = api_instance.get_recipe_information(ids, include_nutrition=include_nutrition)
#             response_dict = [result.to_dict() for result in api_response]
#             print("The response of RecipesApi->get_recipe_information:\n")
#             return jsonify(response_dict)
#         except Exception as e:
#             print("Exception when calling RecipesApi->get_recipe_information: %s\n" % e)
#     return


@app.route("/users", methods=["GET"])
def user_list():
    age = int(request.args.get("age"))
    users = list(db.users.find({"age": {"$gt": age}}, {"_id": False}))
    return jsonify({"users": users})


# @app.route('/upload ', methods=['POST'])
# def upload_image():
#     if 'file' not in request.files:
#         return jsonify({'error': 'No file part'})
#
#     file = request.files['file']
#
#     if file.filename == '':
#         return jsonify({'error': 'No selected file'})
#
#     if file:
#         filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#         file.save(filename)
#         return jsonify({'message': 'file uploaded!'})


@app.route("/upload_and_find", methods=['POST'])
def upload_and_find():
    if 'file' not in request.files:
        return jsonify({'error': '파일 부분이 없습니다.'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': '선택된 파일이 없습니다.'})

    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        try:
            # YOLOv8 모델을 사용하여 이미지 처리 및 객체 인식
            results = model(filename)

            # YOLOv8 모델의 클래스 이름 리스트 가져오기
            class_names = model.names

            # 객체 이름 추출
            detected_objects = []
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls)
                    class_name = class_names[class_id]
                    detected_objects.append(class_name)

            ingredients = ','.join(set(detected_objects))  # 중복 제거 후 콤마로 구분된 문자열로 변환
            print("Detected ingredients:", ingredients)

            # Spoonacular API 호출 부분
            with spoonacular.ApiClient(configuration) as api_client:
                api_instance = spoonacular.RecipesApi(api_client)
                limit_license = True
                ranking = 1
                ignore_pantry = False

                try:
                    api_response = api_instance.search_recipes_by_ingredients(
                        ingredients=ingredients,
                        number=2,
                        limit_license=limit_license,
                        ranking=ranking,
                        ignore_pantry=ignore_pantry
                    )
                    response_dict = [result.to_dict() for result in api_response]
                    jsonieddict = jsonify(response_dict)

                    api_instance = api_instance.get_recipe_information(ids, include_nutrition=include_nutrition)
                    return jsonieddict

                except Exception as e:
                    print("RecipesApi를 호출하는 동안 예외 발생: %s\n" % e)
                    return jsonify({"error": str(e)}), 500

        except Exception as e:
            print("YOLOv8으로 이미지 처리 중 예외 발생: %s\n" % e)
            return jsonify({"error": "YOLOv8으로 이미지 처리 중 오류 발생"}), 500

    return jsonify({"error": "알 수 없는 오류가 발생했습니다"}), 500


if __name__ == '__main__':
    app.run(host='192.168.45.115', port=5000)
