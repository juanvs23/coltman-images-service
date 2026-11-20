# DreamShaper XL base — informe de investigación

**Estado:** solo investigación. No se descargó ningún peso, no se tocó runtime, no se cambió ningún artefacto del proyecto.  
**Fecha:** 2026-11-18  
**Rol en la criba:** candidato de estilo/ecosistema, no candidato principal de licencia ni de memoria.  
**Nota de alcance:** este informe cubre **DreamShaper XL base (alpha2 / xl1.0)**, no las variantes Turbo ni Lightning. Las variantes destiladas se tratan por separado.

---

## 1. Qué es

DreamShaper XL base es un **fine-tune de SDXL 1.0** creado por Lykon. No es un modelo destilado ni un acelerador; es un checkpoint generalista orientado a:

- fotografía,
- arte,
- anime,
- cómic,
- estilos generales.

El autor lo describe como un modelo que intenta “hacer de todo bien”. Es comparable en espíritu a otros generalistas de SDXL.

### 1.1 Variante tratada aquí
- **Base / alpha2 (xl1.0)**
  - fine-tune sobre SDXL 1.0
  - sin destilación agresiva
  - no es Turbo
  - no es Lightning

---

## 2. Peso real en disco

### 2.1 Artefacto oficial de componentes
El repositorio oficial `Lykon/dreamshaper-xl-1-0` no publica un único archivo all-in-one; publica componentes separados:

| Componente | Tamaño |
|---|---:|
| `unet/diffusion_pytorch_model.fp16.safetensors` | 5.14 GB |
| `text_encoder/model.fp16.safetensors` | 246 MB |
| `text_encoder_2/model.fp16.safetensors` | 1.39 GB |
| `vae/diffusion_pytorch_model.fp16.safetensors` | 314 MB |
| **Total práctico (fp16, sin duplicados)** | **≈6.94 GB** |
| **Total del repo completo** | **≈20.96 GB** |

El repo completo pesa ~20.96 GB porque incluye **fp16 y fp32 duplicados**.

### 2.2 Alternativa single-file
Existe un mirror de terceros con un archivo all-in-one:

- `dreamshaperXL_alpha2Xl10.safetensors` ≈ **6.94 GB**

Ese archivo no pertenece al repo oficial de Lykon, por lo que:
- su provenance es de terceros,
- debe pinarse con `sha256`,
- y no debe asumirse como oficial sin verificación.

### 2.3 Lectura operativa
- **Costo operativo real:** ≈ **6.94 GB** en fp16.
- **Costo repo completo:** ≈ **20.96 GB** si se clona todo.
- **No hay una versión base INT8/GGUF oficial** en el repo de Lykon.

---

## 3. INT8 / GGUF

### 3.1 Base
- **No se encontró una versión base DreamShaper XL 1.0 en GGUF/INT8** en el repositorio oficial ni en una fuente de terceros claramente documentada en esta investigación.
- El checkpoint base existe como:
  - componentes fp16 en el repo oficial,
  - o un mirror single-file de terceros (~6.94 GB).

### 3.2 Variantes destiladas
Sí existen versiones GGUF de terceros para **DreamShaper XL v2 Turbo**, pero **no para la base**:

| Artefacto | Cuantización | Tamaño |
|---|---|---:|
| `off-grid-ai/dreamshaper-xl-v2-turbo-GGUF` | **Q8_0** | 4.18 GB |
| `off-grid-ai/dreamshaper-xl-v2-turbo-GGUF` | **Q4_K_S** | 2.80 GB |

Estos archivos:
- **no son la base**,
- corresponden a la variante **Turbo**,
- heredan **OpenRAIL++**,
- y no resuelven el problema de la base.

### 3.3 Conclusión
Si el objetivo es una versión liviana de **DreamShaper XL base**, no hay ruta cuantizada verificada.  
Lo liviano que existe en el ecosistema pertenece a las variantes **Turbo/Lightning**, no a la base.

---

## 4. Licencia

- **CreativeML Open RAIL++-M / OpenRAIL++**
- Es una licencia de uso responsable, no Apache 2.0.
- Permite uso comercial y público en general, con restricciones de uso aceptable.
- No se encontró una cláusula de “no comercial” para la **base**; la advertencia de permiso comercial aparece asociada a la variante **Turbo**, no a la base.
- Si se usa un mirror de terceros, la licencia sigue siendo la del modelo original, pero la provenance debe verificarse.

---

## 5. Memoria y 720p

- DreamShaper XL base comparte la arquitectura y el peso de SDXL 1.0.
- Peso operativo: ~**6.94 GB** en fp16.
- No hay medición de `load_only` ni `warm_render` en este proyecto.
- Al ser un fine-tune de SDXL base, se espera un consumo de memoria similar a SDXL base, no a un modelo destilado.
- Puede renderizar a `1280×720` en principio, pero el pico real debe medirse.
- No hay evidencia de que la base quepa holgada en una tarjeta de 8 GB con margen para LoRAs.

---

## 6. Compatibilidad con LoRAs

- Al ser un fine-tune de SDXL 1.0, la compatibilidad con LoRAs SDXL es **alta**.
- No hay recorte de arquitectura como en SSD-1B o Vega.
- Se espera que los LoRAs SDXL encajen estructuralmente con mayor facilidad que en modelos destilados.
- Aún así:
  - debe probarse el key mapping,
  - el efecto debe ser visible,
  - y un stack de varios LoRAs puede alterar la calidad.

---

## 7. Pros

- Modelo **generalista** con buen rendimiento en fotos, arte, anime y cómic.
- **Arquitectura SDXL 1.0** intacta.
- **Buena compatibilidad con LoRAs SDXL** y con el ecosistema existente.
- **Negative prompt y CFG funcionales** en la base.
- No es una variante destilada, por lo que no tiene las restricciones de CFG 1/2 de Turbo o Lightning.
- Licencia OpenRAIL++-M, con uso comercial posible bajo restricciones de uso aceptable.

---

## 8. Contras

- **No es Apache 2.0.**
- **Peso alto:** ~6.94 GB en fp16.
- **No hay versión base INT8/GGUF verificada.**
- El repo oficial es de componentes, no single-file.
- Si se usa un mirror single-file, la provenance es de terceros.
- El autor recomienda usar **Turbo o Lightning** para trabajo nuevo, lo que sugiere que la base ya no es el foco de mantenimiento.
- La memoria esperada es similar a SDXL base, lo que lo hace menos atractivo si el criterio principal es holgura de VRAM.

---

## 9. Descripción como producto

- **Tipo:** fine-tune generalista de SDXL 1.0.
- **Uso principal:** generación de imágenes en múltiples estilos con un solo checkpoint.
- **Perfil ideal:**
  - arte generalista,
  - anime,
  - fotografía estilizada,
  - cómic,
  - escenas donde se quiere un checkpoint “todo terreno”.
- **No es ideal para:**
  - máxima velocidad,
  - mínima memoria,
  - flujos que exijan Apache 2.0,
  - casos donde se busque una versión cuantizada ligera.

---

## 10. Resumen de Stage 2

### Pass si
- se acepta la licencia OpenRAIL++-M,
- el peso operativo es ~6.94 GB y el pico medido cabe en `1280×720`,
- un LoRA cambia la salida de forma medible,
- un stack de 3 LoRAs no rompe el presupuesto,
- cleanup es limpio,
- y no se requiere una versión cuantizada para que quepa.

### Kill si
- el pico de inferencia no cabe con margen,
- la ausencia de base GGUF/INT8 impide cumplir el presupuesto de memoria,
- la calidad no justifica el costo frente a SDXL canonical,
- o la licencia no se acepta.

---

## 11. Conclusión

- DreamShaper XL **base** es un buen candidato de **estilo y compatibilidad LoRA**, no de memoria.
- No hay una versión cuantizada liviana de la base.
- Su peso operativo es similar a SDXL base (~6.94 GB).
- Si el objetivo es memoria, este candidato **no mejora** el panorama frente a SDXL canonical.
- Si el objetivo es estilo generalista con LoRAs SDXL, sí es un candidato razonable.
- B3 sigue abierto. P10 sigue planned. Stage 2 no se ha ejecutado.

