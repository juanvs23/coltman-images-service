# DreamShaper XL Lightning — informe de investigación

**Estado:** solo investigación. No se descargó ningún peso, no se tocó runtime, no se cambió ningún artefacto del proyecto.  
**Fecha:** 2026-11-18  
**Rol en la criba:** candidato de estilo/ecosistema con enfoque de pocos pasos.  
**Motivo del análisis:** evaluar la variante Lightning de DreamShaper XL como modelo base de baja latencia, con foco en licencia, disco, memoria, 720p y compatibilidad LoRA.

---

## 1. Qué es

`DreamShaper XL Lightning` es una variante destilada de DreamShaper XL, creada por Lykon a partir de la familia **SDXL Lightning**. No es un modelo base nuevo ni un acelerador tipo LoRA; es un **checkpoint de pocos pasos** orientado a generar imágenes de forma rápida manteniendo un perfil generalista.

### 1.1 Qué lo distingue de otras variantes
- **DreamShaper XL base (alpha2 / xl1.0)**: checkpoint generalista sin destilación agresiva.
- **DreamShaper XL Lightning**: checkpoint destilado de pocos pasos, actual enfoque del autor.
- **DreamShaper XL Turbo**: checkpoint de pocos pasos con advertencia comercial explícita de permiso de Stability AI; **no es el caso de Lightning**.

---

## 2. Peso real en disco

### 2.1 Artefacto principal
El archivo principal publicado por el autor es:

- `DreamShaperXL_Lightning.safetensors`
- Tamaño: **6,939,220,250 bytes** ≈ **6.94 GB** / **6.46 GiB**

También existe una variante SFW:

- `DreamShaperXL_Lightning-SFW.safetensors`
- Tamaño: **6.94 GB**

### 2.2 Repo completo
El repositorio completo de Hugging Face pesa alrededor de **34.7 GB**, porque incluye componentes en fp32 y fp16 duplicados. Para uso operativo no es necesario clonar todo; basta el **single-file de ~6.94 GB**.

### 2.3 Lectura operativa
- **Costo operativo real:** **≈6.94 GB**
- **Formato:** `safetensors` single-file
- **No hay dependencias ocultas obligatorias** si se usa el checkpoint único en un runtime compatible (ComfyUI / Diffusers)
- Si se usa la versión en componentes de Diffusers, entonces sí se necesitan los sidecars del repo

---

## 3. Licencia

- **CreativeML Open RAIL++-M / `openrail++`**
- Permite uso comercial y publicitario.
- No es Apache 2.0.
- A diferencia de la variante **Turbo**, el autor **no publica una advertencia de “permiso de Stability AI para uso comercial”** en Lightning.
- La restricción es de uso responsable:
  - no usar el modelo para contenido ilegal o dañino,
  - no usarlo para acoso, difamación, engaño o contenido que vulnere derechos,
  - mantener la licencia si redistribuyes el modelo o derivados.

### 3.1 Comparación rápida con Turbo
| Variante | Licencia | Advertencia comercial explícita |
|---|---|---|
| **DreamShaper XL Lightning** | OpenRAIL++-M | **No** |
| **DreamShaper XL Turbo** | OpenRAIL++-M | **Sí** — “no usar comercialmente sin permiso de Stability AI” |

---

## 4. INT8 / GGUF

### 4.1 Versión oficial
- **No se encontró una versión oficial INT8 o GGUF** de DreamShaper XL Lightning publicada por Lykon.
- El checkpoint oficial es fp16 single-file de ~6.94 GB.

### 4.2 Terceros
Sí existe al menos una conversión de terceros directamente etiquetada como cuantización de **DreamShaper XL Lightning**:

- `Solictous/dreamshaper-xl-lightning-GGUF`
  - archivo: `DreamShaperXL_Lightning-SFW_q5_1.gguf`
  - tamaño: **4,157,060,224 bytes** ≈ **4.16 GB**
  - formato: **GGUF Q5_1**
  - base declarada: `Lykon/dreamshaper-xl-lightning`
  - nota: corresponde a la variante **SFW** del checkpoint Lightning; no se encontró en ese mismo repo una versión no-SFW ni Q4/Q8.

También existen otras conversiones de terceros, pero son **específicas de otra plataforma** y no equivalen a un artefacto GGUF directo para `stable-diffusion.cpp`:

- `HelloSun/dreamshaper-xl-lightning-OpenVINO-INT4`
  - OpenVINO INT4, total del repo ≈ **2.1 GB**
  - no es un checkpoint GGUF; es un pipeline OpenVINO
- `Gatchamn/coreml-dreamshaper-xl-lightning-8bit`
  - CoreML 8-bit, total ≈ **3.6 GB**
- `MefjuDevLLC/coreml-dreamshaper-xl-lightning-6bit`
  - CoreML 6-bit, total ≈ **3.0 GB**
- `amd/dreamshaper-xl-lightning_io16_amdgpu`
  - ONNX optimizado para AMD, no genérico

Otras conversiones de la familia, **no equivalentes a Lightning**:
- `off-grid-ai/dreamshaper-xl-v2-turbo-GGUF` → Q8_0 **4.18 GB** / Q4_K_S **2.80 GB** (Turbo, no Lightning)
- `mzwing/SDXL-Lightning-GGUF` → Q4/Q5/Q8 de SDXL-Lightning, no DreamShaper
- `darkmaniac7/TokForge-RealVisXL-Lightning-GGUF` → RealVisXL Lightning, no DreamShaper

### 4.3 Conclusión
- Sí hay **una tercera parte GGUF** directamente utilizable para Lightning:
  - **Q5_1 ~4.16 GB**, en la variante SFW.
- No se encontró en esa misma fuente una versión **Q4** ni **Q8** de Lightning.
- No hay un artefacto oficial cuantizado de Lykon.
- Si se necesita una versión no-SFW en GGUF, habría que generarla manualmente o buscar otra conversión no identificada en esta investigación.

---

## 5. Memoria y 720p

- El checkpoint pesa **~6.94 GB** en disco.
- No hay medición de `load_only` ni `warm_render` en este proyecto.
- Al ser un checkpoint SDXL destilado, el consumo de memoria se espera similar a otros modelos SDXL de 3B, con la ventaja de **menos pasos de inferencia**.
- Puede renderizar a `1280×720` en principio, pero el pico real debe medirse.
- No hay evidencia pública de que el modelo quepa holgado en una tarjeta de 8 GB con margen para LoRAs.

### 5.1 Qué se gana con pocos pasos
- Menor latencia
- Menos iteraciones de denoise
- Posible mejor throughput en comparación con SDXL base

### 5.2 Qué no se garantiza
- Que el pico de VRAM baje proporcionalmente al número de pasos
- Que 720p con LoRAs tenga margen suficiente en 8 GB
- Que la calidad no degradada en microdetalle

---

## 6. Compatibilidad con LoRAs

- DreamShaper XL Lightning es un **fine-tune de SDXL**, por lo que se espera **compatibilidad alta** con LoRAs SDXL.
- No hay recorte de arquitectura como en SSD-1B o Vega.
- El autor no declara incompatibilidad con LoRAs.
- Aún así:
  - se deben probar las keys,
  - el efecto debe ser visible,
  - y un stack de varios LoRAs puede alterar la calidad.

### 6.1 Nota sobre negative prompt
- DreamShaper XL Lightning recomienda **CFG ≈ 2** y **3–6 pasos**.
- A CFG 2, los negative prompts pueden tener efecto parcial.
- No se espera un comportamiento tan robusto como en SDXL base con CFG 5–8.
- Este punto debe medirse en Stage 2 si se convierte en criterio.

---

## 7. Pros

- Variante **Lightning** de DreamShaper XL, con foco en pocos pasos.
- **Latencia baja** comparada con DreamShaper XL base.
- **OpenRAIL++-M**, comercial utilizable sin la advertencia específica de Turbo.
- **Compatibilidad alta** con LoRAs SDXL.
- **Arquitectura SDXL** intacta, sin recorte agresivo.
- Single-file oficial de **~6.94 GB**, sin dependencias ocultas si se usa en runtime compatible.
- Comunidad amplia y revisiones positivas.
- Existe variante SFW.

---

## 8. Contras

- **No es Apache 2.0.**
- **Peso alto:** ~6.94 GB.
- **No hay versión oficial INT8/GGUF.**
- El repo completo pesa ~34.7 GB, aunque el artefacto operativo sea single-file.
- La memoria esperada sigue siendo similar a SDXL, no a un modelo ultraligero.
- El negative prompt puede ser menos efectivo que en SDXL base.
- Aún no hay medición de pico a `1280×720`.
- No hay garantía de margen para LoRAs sin Stage 2.

---

## 9. Descripción como producto

- **Tipo:** checkpoint destilado de pocos pasos basado en SDXL.
- **Uso principal:** generación rápida de imágenes de estilo generalista.
- **Perfil ideal:**
  - arte generalista,
  - anime,
  - fotografía estilizada,
  - cómic,
  - escenas donde se quiere un checkpoint “todo terreno” con menos pasos.
- **No es ideal para:**
  - máxima fidelidad de microdetalle,
  - mínima memoria,
  - flujos que exijan Apache 2.0,
  - casos donde se busque una versión cuantizada oficial.

---

## 10. Stage 2

### Pass si
- se acepta la licencia OpenRAIL++-M,
- el pico medido cabe en `1280×720` con margen,
- un LoRA cambia la salida de forma medible,
- un stack de 3 LoRAs no rompe el presupuesto,
- cleanup es limpio,
- y la calidad en 3–6 pasos es aceptable frente a los anchors actuales.

### Kill si
- el pico de inferencia no cabe con margen,
- la ausencia de versión cuantizada impide cumplir el presupuesto de memoria,
- la calidad en 3–6 pasos no justifica el costo frente a SDXL-Lightning o SDXL canonical,
- o la licencia no se acepta.

---

## 11. Conclusión

- DreamShaper XL **Lightning** es un buen candidato de **estilo y velocidad** dentro de la familia SDXL.
- Su licencia es comercial utilizable, sin la advertencia específica de Turbo.
- Peso operativo: **~6.94 GB**.
- No hay versión cuantizada oficial; existe una conversión de terceros **GGUF Q5_1 ~4.16 GB** (variante SFW).
- La compatibilidad con LoRas SDXL es alta.
- B3 sigue abierto. P10 sigue planned. Stage 2 no se ha ejecutado.

