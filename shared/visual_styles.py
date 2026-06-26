"""
Catalogo de estilos visuales para FLUX.1-schnell
=================================================

Prompts base tomados de Fooocus (github.com/lllyasviel/Fooocus),
curados y organizados para canales de YouTube.

Cada estilo tiene un prompt_template con {prompt} como placeholder
y un negative_prompt. La funcion aplicar_estilo() reemplaza {prompt}
por la descripcion de la escena. FLUX no usa negative_prompt
directamente pero se mantiene para compatibilidad con otros modelos.
"""

from __future__ import annotations

CATEGORIAS: list[dict] = [
    {"slug": "realista", "nombre": "Realista / Fotografico"},
    {"slug": "anime-cartoon", "nombre": "Anime / Cartoon"},
    {"slug": "artistico", "nombre": "Artistico"},
    {"slug": "digital-futurista", "nombre": "Digital / Futurista"},
    {"slug": "atmosfera-mood", "nombre": "Atmosfera / Mood"},
    {"slug": "youtube-especial", "nombre": "Especiales YouTube"},
]

CATALOGO_ESTILOS: list[dict] = [
    # ── Realista / Fotografico ──────────────────────────────────────
    {
        "slug": "photorealistic",
        "nombre": "Realista / Fotografico",
        "categoria": "realista",
        "prompt_template": (
            "cinematic photo {prompt} . 35mm photograph, film, bokeh, "
            "professional, 4k, highly detailed"
        ),
        "negative_prompt": (
            "drawing, painting, crayon, sketch, graphite, impressionist, "
            "noisy, blurry, soft, deformed, ugly"
        ),
        "caso_uso": "Canales educativos, documentales, noticias",
    },
    {
        "slug": "cinematic",
        "nombre": "Cinematico",
        "categoria": "realista",
        "prompt_template": (
            "cinematic film still {prompt} . shallow depth of field, vignette, "
            "highly detailed, high budget, bokeh, cinemascope, moody, epic, "
            "gorgeous, film grain, grainy"
        ),
        "negative_prompt": (
            "anime, cartoon, graphic, text, painting, crayon, graphite, "
            "abstract, glitch, deformed, mutated, ugly, disfigured"
        ),
        "caso_uso": "Storytelling, reseñas, vlogs cinematicos",
    },
    {
        "slug": "film-noir",
        "nombre": "Film Noir",
        "categoria": "realista",
        "prompt_template": (
            "film noir style {prompt} . monochrome, high contrast, dramatic "
            "shadows, 1940s style, mysterious, cinematic"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic, vibrant, colorful"
        ),
        "caso_uso": "Misterio, crimen, historias oscuras",
    },
    {
        "slug": "analog-vintage",
        "nombre": "Analog Film / Vintage",
        "categoria": "realista",
        "prompt_template": (
            "analog film photo {prompt} . faded film, desaturated, 35mm photo, "
            "grainy, vignette, vintage, Kodachrome, Lomography, stained, "
            "highly detailed, found footage"
        ),
        "negative_prompt": (
            "painting, drawing, illustration, glitch, deformed, mutated, "
            "cross-eyed, ugly, disfigured"
        ),
        "caso_uso": "Nostalgia, retro, historia",
    },
    {
        "slug": "neon-noir",
        "nombre": "Neon Noir",
        "categoria": "realista",
        "prompt_template": (
            "neon noir {prompt} . cyberpunk, dark, rainy streets, neon signs, "
            "high contrast, low light, vibrant, highly detailed"
        ),
        "negative_prompt": (
            "bright, sunny, daytime, low contrast, black and white, sketch, "
            "watercolor"
        ),
        "caso_uso": "Tech, gaming nocturno, urban",
    },
    {
        "slug": "hdr",
        "nombre": "HDR Photography",
        "categoria": "realista",
        "prompt_template": (
            "HDR photo of {prompt} . High dynamic range, vivid, rich details, "
            "clear shadows and highlights, realistic, intense, enhanced "
            "contrast, highly detailed"
        ),
        "negative_prompt": (
            "flat, low contrast, oversaturated, underexposed, overexposed, "
            "blurred, noisy"
        ),
        "caso_uso": "Viajes, naturaleza, arquitectura",
    },
    # ── Anime / Cartoon ─────────────────────────────────────────────
    {
        "slug": "anime",
        "nombre": "Anime",
        "categoria": "anime-cartoon",
        "prompt_template": (
            "anime artwork {prompt} . anime style, key visual, vibrant, "
            "studio anime, highly detailed"
        ),
        "negative_prompt": (
            "photo, deformed, black and white, realism, disfigured, "
            "low contrast"
        ),
        "caso_uso": "Anime reviews, storytime animado",
    },
    {
        "slug": "manga",
        "nombre": "Manga",
        "categoria": "anime-cartoon",
        "prompt_template": (
            "manga artwork presenting {prompt}. created by japanese manga "
            "artist. highly emotional. best quality, high resolution"
        ),
        "negative_prompt": "low quality, low resolution",
        "caso_uso": "Manga/comic content",
    },
    {
        "slug": "kawaii",
        "nombre": "Kawaii",
        "categoria": "anime-cartoon",
        "prompt_template": (
            "kawaii style {prompt} . cute, adorable, brightly colored, "
            "cheerful, anime influence, highly detailed"
        ),
        "negative_prompt": "dark, scary, realistic, monochrome, abstract",
        "caso_uso": "Contenido cute, infantil, lifestyle",
    },
    {
        "slug": "cel-shaded",
        "nombre": "Cartoon / Cel Shading",
        "categoria": "anime-cartoon",
        "prompt_template": (
            "Cel Shaded Art, {prompt}, 2D, flat color, toon shading, "
            "cel shaded style"
        ),
        "negative_prompt": "ugly, deformed, noisy, blurry, low contrast",
        "caso_uso": "Entretenimiento, humor, niños",
    },
    {
        "slug": "3d-character",
        "nombre": "3D Character",
        "categoria": "anime-cartoon",
        "prompt_template": (
            "Adorable 3D Character, {prompt}, 3D render, adorable character, "
            "3D art"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, grunge, sloppy, "
            "unkempt, photograph, photo, realistic"
        ),
        "caso_uso": "Infantil, gaming, educativo para niños",
    },
    # ── Artistico ───────────────────────────────────────────────────
    {
        "slug": "watercolor",
        "nombre": "Acuarela",
        "categoria": "artistico",
        "prompt_template": (
            "watercolor painting {prompt} . vibrant, beautiful, painterly, "
            "detailed, textural, artistic"
        ),
        "negative_prompt": (
            "anime, photorealistic, 35mm film, deformed, glitch, "
            "low contrast, noisy"
        ),
        "caso_uso": "Lifestyle, arte, meditacion",
    },
    {
        "slug": "oil-painting",
        "nombre": "Pintura al Oleo",
        "categoria": "artistico",
        "prompt_template": (
            "oil painting {prompt} . rich textures, visible brushstrokes, "
            "deep color tones, classical art, dramatic lighting, "
            "gallery quality"
        ),
        "negative_prompt": (
            "anime, photorealistic, 3D, render, cartoon, flat, low quality, "
            "blurry, deformed"
        ),
        "caso_uso": "Arte, historia, premium feel",
    },
    {
        "slug": "pop-art",
        "nombre": "Pop Art",
        "categoria": "artistico",
        "prompt_template": (
            "pop Art style {prompt} . bright colors, bold outlines, popular "
            "culture themes, ironic or kitsch"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic, minimalist"
        ),
        "caso_uso": "Entretenimiento, cultura pop",
    },
    {
        "slug": "impressionist",
        "nombre": "Impresionismo",
        "categoria": "artistico",
        "prompt_template": (
            "impressionist painting {prompt} . loose brushwork, emphasis on "
            "light and color, dreamy atmosphere, painterly"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic"
        ),
        "caso_uso": "Arte, viajes, cocina artistica",
    },
    {
        "slug": "surrealist",
        "nombre": "Surrealismo",
        "categoria": "artistico",
        "prompt_template": (
            "surrealist art {prompt} . dreamlike, mysterious, provocative, "
            "symbolic, intricate, detailed"
        ),
        "negative_prompt": (
            "anime, photorealistic, realistic, deformed, glitch, noisy, "
            "low contrast"
        ),
        "caso_uso": "Creativo, filosofico, psicologia",
    },
    {
        "slug": "graffiti",
        "nombre": "Graffiti",
        "categoria": "artistico",
        "prompt_template": (
            "graffiti style {prompt} . street art, vibrant, urban, detailed, "
            "tag, mural"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic"
        ),
        "caso_uso": "Urban, hip-hop, street culture",
    },
    # ── Digital / Futurista ─────────────────────────────────────────
    {
        "slug": "cyberpunk",
        "nombre": "Cyberpunk",
        "categoria": "digital-futurista",
        "prompt_template": (
            "cyberpunk cityscape {prompt} . neon lights, dark alleys, "
            "skyscrapers, futuristic, vibrant colors, high contrast, "
            "highly detailed"
        ),
        "negative_prompt": (
            "natural, rural, deformed, low contrast, black and white, "
            "sketch, watercolor"
        ),
        "caso_uso": "Tech, gaming, sci-fi",
    },
    {
        "slug": "neonpunk",
        "nombre": "Neon / Neonpunk",
        "categoria": "digital-futurista",
        "prompt_template": (
            "neonpunk style {prompt} . cyberpunk, vaporwave, neon, vibes, "
            "vibrant, stunningly beautiful, crisp, detailed, sleek, "
            "ultramodern, magenta highlights, dark purple shadows, high "
            "contrast, cinematic, ultra detailed, intricate, professional"
        ),
        "negative_prompt": (
            "painting, drawing, illustration, glitch, deformed, mutated, "
            "cross-eyed, ugly, disfigured"
        ),
        "caso_uso": "Gaming, musica electronica, tech",
    },
    {
        "slug": "vaporwave",
        "nombre": "Vaporwave",
        "categoria": "digital-futurista",
        "prompt_template": (
            "vaporwave style {prompt} . retro aesthetic, cyberpunk, vibrant, "
            "neon colors, vintage 80s and 90s style, highly detailed"
        ),
        "negative_prompt": (
            "monochrome, muted colors, realism, rustic, minimalist, dark"
        ),
        "caso_uso": "Retro-tech, aesthetic, musica",
    },
    {
        "slug": "sci-fi",
        "nombre": "Sci-Fi",
        "categoria": "digital-futurista",
        "prompt_template": (
            "sci-fi style {prompt} . futuristic, technological, alien worlds, "
            "space themes, advanced civilizations"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic, historical, medieval"
        ),
        "caso_uso": "Ciencia, espacio, futurismo",
    },
    {
        "slug": "3d-render",
        "nombre": "3D Render",
        "categoria": "digital-futurista",
        "prompt_template": (
            "professional 3d model {prompt} . octane render, highly detailed, "
            "volumetric, dramatic lighting"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, low poly, blurry, painting"
        ),
        "caso_uso": "Tech, productos, educativo",
    },
    {
        "slug": "pixel-art",
        "nombre": "Pixel Art",
        "categoria": "digital-futurista",
        "prompt_template": (
            "pixel-art {prompt} . low-res, blocky, pixel art style, "
            "8-bit graphics"
        ),
        "negative_prompt": (
            "sloppy, messy, blurry, noisy, highly detailed, ultra textured, "
            "photo, realistic"
        ),
        "caso_uso": "Gaming retro, nostalgia, indie",
    },
    {
        "slug": "isometric",
        "nombre": "Isometrico",
        "categoria": "digital-futurista",
        "prompt_template": (
            "isometric style {prompt} . vibrant, beautiful, crisp, detailed, "
            "ultra detailed, intricate"
        ),
        "negative_prompt": (
            "deformed, mutated, ugly, disfigured, blur, blurry, noise, "
            "noisy, realistic, photographic"
        ),
        "caso_uso": "Tech, explicaciones, infografias",
    },
    # ── Atmosfera / Mood ────────────────────────────────────────────
    {
        "slug": "dark-fantasy",
        "nombre": "Dark Fantasy",
        "categoria": "atmosfera-mood",
        "prompt_template": (
            "Dark Fantasy Art, {prompt}, dark, moody, dark fantasy style"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, bright, sunny"
        ),
        "caso_uso": "Horror, fantasia oscura, misterio",
    },
    {
        "slug": "fantasy-art",
        "nombre": "Fantasy Art",
        "categoria": "atmosfera-mood",
        "prompt_template": (
            "ethereal fantasy concept art of {prompt} . magnificent, "
            "celestial, ethereal, painterly, epic, majestic, magical, "
            "fantasy art, cover art, dreamy"
        ),
        "negative_prompt": (
            "photographic, realistic, realism, 35mm film, dslr, cropped, "
            "frame, text, deformed, glitch, noise, noisy, off-center, "
            "deformed, cross-eyed, closed eyes, bad anatomy, ugly, "
            "disfigured, sloppy, duplicate, mutated, black and white"
        ),
        "caso_uso": "Fantasia, RPG, worldbuilding",
    },
    {
        "slug": "gothic",
        "nombre": "Gotico",
        "categoria": "atmosfera-mood",
        "prompt_template": (
            "gothic style {prompt} . dark, mysterious, haunting, dramatic, "
            "ornate, detailed"
        ),
        "negative_prompt": (
            "ugly, deformed, noisy, blurry, low contrast, realism, "
            "photorealistic, cheerful, optimistic"
        ),
        "caso_uso": "Horror, dark aesthetic",
    },
    {
        "slug": "steampunk",
        "nombre": "Steampunk",
        "categoria": "atmosfera-mood",
        "prompt_template": (
            "steampunk style {prompt} . antique, mechanical, brass and copper "
            "tones, gears, intricate, detailed"
        ),
        "negative_prompt": (
            "deformed, glitch, noisy, low contrast, anime, photorealistic"
        ),
        "caso_uso": "Steampunk, alternativo, maker",
    },
    {
        "slug": "minimalist",
        "nombre": "Minimalista",
        "categoria": "atmosfera-mood",
        "prompt_template": (
            "minimalist style {prompt} . simple, clean, uncluttered, "
            "modern, elegant"
        ),
        "negative_prompt": (
            "ornate, complicated, highly detailed, cluttered, disordered, "
            "messy, noisy"
        ),
        "caso_uso": "Productividad, tech clean, diseño",
    },
    # ── Especiales YouTube ──────────────────────────────────────────
    {
        "slug": "whiteboard",
        "nombre": "Stickman / Whiteboard",
        "categoria": "youtube-especial",
        "prompt_template": (
            "whiteboard animation style {prompt} . simple stick figures, "
            "hand-drawn look, white background, black ink lines, educational "
            "diagram, clean minimal sketch"
        ),
        "negative_prompt": (
            "realistic, photographic, detailed, complex background, 3D, "
            "colorful, painting"
        ),
        "caso_uso": "Educativo, explicaciones",
    },
    {
        "slug": "comic-book",
        "nombre": "Comic Book",
        "categoria": "youtube-especial",
        "prompt_template": (
            "comic {prompt} . graphic illustration, comic art, graphic novel "
            "art, vibrant, highly detailed"
        ),
        "negative_prompt": (
            "photograph, deformed, glitch, noisy, realistic, stock photo"
        ),
        "caso_uso": "Storytime, humor, entretenimiento",
    },
    {
        "slug": "infographic",
        "nombre": "Infografia",
        "categoria": "youtube-especial",
        "prompt_template": (
            "Infographic Drawing, {prompt}, diagram, infographic"
        ),
        "negative_prompt": "ugly, deformed, noisy, blurry, low contrast",
        "caso_uso": "Educativo, datos, analisis",
    },
]

_INDICE_POR_SLUG: dict[str, dict] = {e["slug"]: e for e in CATALOGO_ESTILOS}


def obtener_estilo(slug: str) -> dict | None:
    """Retorna el estilo por slug, o None si no existe."""
    return _INDICE_POR_SLUG.get(slug)


def listar_estilos(categoria: str | None = None) -> list[dict]:
    """Retorna estilos, opcionalmente filtrados por categoria."""
    if categoria is None:
        return list(CATALOGO_ESTILOS)
    return [e for e in CATALOGO_ESTILOS if e["categoria"] == categoria]


def listar_categorias() -> list[dict]:
    """Retorna las categorias disponibles."""
    return list(CATEGORIAS)


def aplicar_estilo(slug: str, prompt: str) -> tuple[str, str]:
    """Aplica el template del estilo al prompt.

    Retorna (prompt_positivo, negative_prompt).
    Para slug 'custom', retorna el prompt tal cual con negative vacio.
    """
    if slug == "custom":
        return prompt, ""
    estilo = _INDICE_POR_SLUG.get(slug)
    if estilo is None:
        return prompt, ""
    prompt_positivo = estilo["prompt_template"].replace("{prompt}", prompt)
    return prompt_positivo, estilo["negative_prompt"]


def aplicar_estilo_custom(
    prompt_template: str, negative_prompt: str, prompt: str
) -> tuple[str, str]:
    """Aplica un template custom (para estilo 'custom' o identidad de canal)."""
    prompt_positivo = prompt_template.replace("{prompt}", prompt)
    return prompt_positivo, negative_prompt
