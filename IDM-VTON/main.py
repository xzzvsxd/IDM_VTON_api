import base64
import io
import time

from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app_VTON import start_tryon

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，实际应用中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

class TryonRequest(BaseModel):
    pose_type: str = "upper_body"
    preserve_background: bool = True
    inpaint_face: bool = True
    n_trials: int = 30
    use_input_pose: bool = True
    smooth_mask: int = 1
    smooth_face: int = 1

@app.post("/tryon")
async def tryon(
    input_img: UploadFile = File(...),
    cloth_img: UploadFile = File(...),
    pose_type: str = Form("upper_body"),
    preserve_background: bool = Form(True),
    inpaint_face: bool = Form(True),
    n_trials: int = Form(30),
    use_input_pose: bool = Form(True),
    smooth_mask: int = Form(1),
    smooth_face: int = Form(1)
):
    try:
        # 读取上传的文件
        input_img_content = await input_img.read()
        cloth_img_content = await cloth_img.read()

        # 将文件内容转换为 PIL Image 对象
        human_img = Image.open(io.BytesIO(input_img_content))
        garm_img = Image.open(io.BytesIO(cloth_img_content))

        # 保存原始人物图像和服装图像
        human_img.save("human_image_original.png")
        garm_img.save("garment_image.png")

        # 处理透明通道
        if human_img.mode in ('RGBA', 'LA') or (human_img.mode == 'P' and 'transparency' in human_img.info):
            background = Image.new('RGBA', human_img.size, (255, 255, 255, 255))
            if human_img.mode == 'P':
                human_img = human_img.convert('RGBA')
            human_img = Image.alpha_composite(background, human_img)
            human_img = human_img.convert('RGB')

        # 保存处理透明通道后的图像
        human_img.save("human_image_white_bg.png")

        # 获取原始图像的尺寸
        width, height = human_img.size

        # 计算裁剪的参数
        target_width, target_height = 768, 1024
        left = (width - target_width) // 2
        top = 0
        right = left + target_width
        bottom = min(height, target_height)  # 确保不会裁剪超出图像底部

        # 裁剪图像
        human_img_cropped = human_img.crop((left, top, right, bottom))

        # 如果裁剪后的高度小于1024，创建一个新的白色背景图像并粘贴裁剪后的图像
        if bottom < target_height:
            new_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            new_img.paste(human_img_cropped, (0, 0))
            human_img_cropped = new_img

        # 保存裁剪后的图像
        human_img_cropped.save("human_image_cropped.png")

        # 调用 start_tryon 函数
        result = start_tryon(
            {"background": human_img},
            garm_img,
            "",
            pose_type,
            preserve_background,
            inpaint_face,
            n_trials,
            use_input_pose,
            smooth_mask,
            smooth_face
        )
        # print(result)

        try:
            # 将结果图片转换为 base64
            result_img = Image.open(result[0][0])
            # print(1)
            result_base64 = image_to_base64(result_img)
            # print(2)
            mask_base64 = image_to_base64(result[1])
            # print(3)
        except:
            import traceback
            traceback.print_exc()

        # 返回结果
        return_content = {
            "result_image": result_base64,
            "mask_image": mask_base64
        }
        # print(return_content)
        # print(time.time())

        return JSONResponse(content=return_content)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8010)