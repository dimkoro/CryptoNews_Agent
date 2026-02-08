import asyncio
from app.core.config import load_config
from app.services.image_service import ImageService


async def main():
    config = load_config()
    img = ImageService(
        provider=config['image_provider'],
        api_key=config['unsplash_key'],
        hf_key=config['hf_key'],
        proxy=config['proxy'],
        hf_model=config['hf_model'],
        hf_width=config['hf_width'],
        hf_height=config['hf_height'],
        fallback_list=config['image_fallbacks']
    )

    prompt = "Bitcoin price surge, bullish market, futuristic crypto city"
    path = await img.get_image(prompt, style_type=config['style_1'])
    if path:
        print(f"OK: {path}")
    else:
        print("FAIL: no image generated")


if __name__ == '__main__':
    asyncio.run(main())
