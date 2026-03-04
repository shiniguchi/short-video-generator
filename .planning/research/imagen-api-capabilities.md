# Google Imagen API Capabilities & Limitations

> Research from hands-on implementation — February 2026

---

## Client Types: Google AI vs Vertex AI

The `google-genai` Python SDK supports two client modes:

```python
# Google AI client (API key) — limited capabilities
client = genai.Client(api_key="AIzaSy...")

# Vertex AI client (GCP project) — full capabilities
client = genai.Client(vertexai=True, project="my-project", location="us-central1")
```

### API Method Availability

| Method | Google AI (API Key) | Vertex AI (GCP) |
|--------|:------------------:|:---------------:|
| `generate_images` (text-to-image) | Yes | Yes |
| `edit_image` (subject refs, sketches, style) | **NO** | Yes |

**This is the critical limitation**: `edit_image` raises `ValueError('This method is only supported in the Vertex AI client.')` when called with an API key client.

### What This Means for ViralForge

- **Text-to-image** (`generate_images`) works with our current `GOOGLE_API_KEY` setup
- **Subject-referenced generation** (product photos as input) requires Vertex AI
- **Sketch-guided generation** (hand-drawn composition control) requires Vertex AI
- **Style transfer** (style reference images) requires Vertex AI

---

## Imagen Reference Image Types

All via `edit_image` API (Vertex AI only):

### SubjectReferenceImage — Product Photos
Preserves the product's actual appearance in the generated image.

```python
ref = types.SubjectReferenceImage(
    reference_id=1,
    reference_image=types.Image.from_file(location="product.png"),
    config=types.SubjectReferenceConfig(
        subject_type=types.SubjectReferenceType.SUBJECT_TYPE_PRODUCT,
        subject_description="a glass sphere candle holder",
    ),
)
```

Subject types: `SUBJECT_TYPE_DEFAULT`, `SUBJECT_TYPE_PERSON`, `SUBJECT_TYPE_ANIMAL`, `SUBJECT_TYPE_PRODUCT`

### ControlReferenceImage — Sketches / Layout Control
Hand-drawn scribbles that control composition and layout.

```python
ref = types.ControlReferenceImage(
    reference_id=2,
    reference_image=types.Image.from_file(location="sketch.png"),
    config=types.ControlReferenceConfig(
        control_type=types.ControlReferenceType.CONTROL_TYPE_SCRIBBLE
    ),
)
```

**Important**: `CONTROL_TYPE_SCRIBBLE` expects line art / hand-drawn sketches. Real photos will be rejected (safety filtered / empty response).

Control types: `CONTROL_TYPE_SCRIBBLE`, `CONTROL_TYPE_CANNY`, `CONTROL_TYPE_FACE_MESH`

### StyleReferenceImage — Style Transfer
Transfers visual style (lighting, color palette, mood) from a reference.

```python
ref = types.StyleReferenceImage(
    reference_id=3,
    reference_image=types.Image.from_file(location="style_ref.png"),
    config=types.StyleReferenceConfig(
        style_description="warm golden hour photography with bokeh",
    ),
)
```

### Combining References
Up to 4 reference images per `edit_image` call. Different types can be combined:

```python
response = client.models.edit_image(
    model="imagen-3.0-capability-001",
    prompt="Hero photo of [1] in composition [2]",
    reference_images=[subject_ref, sketch_ref],  # mixed types
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_DEFAULT,
        number_of_images=1,
        output_mime_type="image/png",
    ),
)
```

Prompt uses `[N]` bracket notation matching `reference_id` values.

### Edit Modes
```
EDIT_MODE_DEFAULT              — general purpose (works with subject/style refs)
EDIT_MODE_CONTROLLED_EDITING   — for scribble/canny control references
EDIT_MODE_STYLE                — for style transfer
EDIT_MODE_PRODUCT_IMAGE        — product background replacement
EDIT_MODE_BGSWAP               — background swap
EDIT_MODE_INPAINT_REMOVAL      — remove objects
EDIT_MODE_INPAINT_INSERTION    — add objects
EDIT_MODE_OUTPAINT             — extend image boundaries
```

### Models
- `imagen-4.0-fast-generate-001` — text-to-image (fast, works with API key)
- `imagen-3.0-capability-001` — edit model (subject refs, sketches, style — Vertex AI only)

---

## Current ViralForge Implementation

### What Works (API Key)
- Initial hero image generation (text-to-image)
- A-Roll / B-Roll scene image generation (text-to-image)
- All mock providers

### What Requires Vertex AI Migration
- Hero image regeneration with product reference photos
- Hero image regeneration with composition sketches
- Combined refs + sketch generation
- Any `edit_image` based feature

### Migration Path to Vertex AI

1. Create GCP project, enable Vertex AI API
2. Create service account with `roles/aiplatform.user`
3. Download service account JSON key
4. Set environment variables:
   ```
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   VERTEX_AI_PROJECT=your-project-id
   VERTEX_AI_LOCATION=us-central1
   ```
5. Update `GoogleImagenProvider.__init__`:
   ```python
   # Check for Vertex AI credentials first, fall back to API key
   if vertex_project:
       self.client = genai.Client(vertexai=True, project=vertex_project, location=vertex_location)
       self.supports_edit = True
   else:
       self.client = genai.Client(api_key=api_key)
       self.supports_edit = False
   ```
6. Guard `edit_image` calls with `self.supports_edit` check
7. Show clear UI message when user tries ref-based generation without Vertex AI

### UI Architecture (Already Implemented)

Two separate upload sections in Overview tab:
- **Reference Photos** — product photos → `SubjectReferenceImage` (preserves product look)
- **Composition Sketches** — hand-drawn sketches → `ControlReferenceImage` (controls layout)

Files stored on disk as:
- `output/ugc_uploads/{job_id}/refphoto_*` — reference photos
- `output/ugc_uploads/{job_id}/sketch_*` — composition sketches

---

## Pricing (as of Feb 2026)

| Operation | Cost |
|-----------|------|
| `generate_images` (text-to-image) | ~$0.04/image |
| `edit_image` (with references) | ~$0.08/image |
| Subject customization (multiple refs) | ~$0.08/image |

---

## Sources

- [Vertex AI Imagen subject customization](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/subject-customization)
- [Vertex AI Imagen style customization](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/style-customization)
- [Imagen API customization reference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-customization)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
