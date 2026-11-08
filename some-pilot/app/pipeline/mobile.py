from app.pipeline.media import MediaError


def mobile_filter(scene, source_width: int, source_height: int, spec, style: str, duration: float) -> str:
    if style not in {"zoom", "safe"}:
        raise MediaError(f"unknown_mobile_style:{style}")
    if style == "safe":
        return (
            "[0:v]split=2[background][foreground];"
            "[background]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=32,eq=brightness=-0.18:saturation=0.8[bg];"
            "[foreground]scale=1040:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[composite];"
        )
    ratios = (0.18, 0.28, 0.20, 0.34)
    parts = []
    for index, ratio in enumerate(ratios):
        phase_duration = duration * ratio
        start = duration * sum(ratios[:index])
        if index in {0, 2}:
            parts.append(f"[0:v]trim=start={start:.3f}:duration={phase_duration:.3f},setpts=PTS-STARTPTS,split=2[bg{index}][fg{index}];")
            parts.append(f"[bg{index}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=28,eq=brightness=-0.18:saturation=0.85[b{index}];")
            parts.append(f"[fg{index}]scale=1040:-2[f{index}];")
            parts.append(f"[b{index}][f{index}]overlay=(W-w)/2:(H-h)/2,fps=30,tpad=stop_mode=clone:stop_duration={phase_duration:.3f},trim=duration={phase_duration:.3f},setpts=N/(30*TB),setsar=1[p{index}];")
        else:
            crop_height = max(2, round(source_height / scene.zoom / 2) * 2)
            crop_width = max(2, round(crop_height * spec.width / spec.height / 2) * 2)
            if crop_width > source_width:
                raise MediaError(f"crop_wider_than_source:{scene.game}")
            x = (source_width - crop_width) * scene.focus_x
            y = (source_height - crop_height) * scene.focus_y
            increment = 0.001 if index == 1 else 0.0013
            maximum = 1.10 if index == 1 else 1.18
            parts.append(f"[0:v]trim=start={start:.3f}:duration={phase_duration:.3f},setpts=PTS-STARTPTS,crop={crop_width}:{crop_height}:{x:.3f}:{y:.3f},zoompan=z='min({maximum},zoom+{increment})':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s=1080x1920:fps=30,tpad=stop_mode=clone:stop_duration={phase_duration:.3f},trim=duration={phase_duration:.3f},setpts=N/(30*TB),setsar=1[p{index}];")
    parts.append("[p0][p1][p2][p3]concat=n=4:v=1:a=0[composite];")
    return "".join(parts)
