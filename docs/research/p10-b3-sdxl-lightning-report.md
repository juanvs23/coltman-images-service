# SDXL-Lightning — informe de investigación

**Estado:** solo investigación. No se descargó ningún peso, no se tocó runtime, no se cambió ningún artefacto del proyecto.  
**Fecha:** 2026-11-18  
**Rol en la criba:** candidato de velocidad, no candidato principal de licencia.  
**Motivo del análisis:** buscar una variante INT8/GGUF más liviana y documentar disco, memoria, LoRA y licencia con la misma estructura usada para SSD-1B, Vega y SDXL canonical.

---

## 1. Qué es

`SDXL-Lightning` es una familia de modelos de texto a imagen **destilados de SDXL base 1.0** por ByteDance. Su objetivo no es ser un nuevo modelo base generalista, sino **reducir drásticamente el número de pasos de inferencia** manteniendo calidad razonable.

### 1.1 Variantes oficiales
El repositorio publica tres tipos de artefactos por cada familia de pasos:

- **All-in-one checkpoint** (modelo completo, para ComfyUI)
- **UNet-only checkpoint** (solo el denoiser, para Diffusers)
- **LoRA checkpoint** (módulo pequeño para aplicar sobre otro SDXL)

Los pasos publicados son:

- **1-step** (experimental)
- **2-step**
- **4-step**
- **8-step**

La tarjeta del modelo indica que **1-step es experimental** y que 2, 4 y 8 pasos tienen buena calidad. El punto de equilibrio más citado por la comunidad es el **4-step**.

---

## 2. Peso real en disco

### 2.1 Artefactos oficiales del repositorio

| Tipo de archivo | Tamaño |
|---|---:|
| `sdxl_lightning_1step_x0.safetensors` (all-in-one) | 6,938,040,682 bytes ≈ **6.94 GB** |
| `sdxl_lightning_2step.safetensors` (all-in-one) | **6.94 GB** |
| `sdxl_lightning_4step.safetensors` (all-in-one) | **6.94 GB** |
| `sdxl_lightning_8step.safetensors` (all-in-one) | **6.94 GB** |
| `sdxl_lightning_1step_unet_x0.safetensors` (UNet-only) | 5,135,149,736 bytes ≈ **5.14 GB** |
| `sdxl_lightning_2step_unet.safetensors` (UNet-only) | **5.14 GB** |
| `sdxl_lightning_4step_unet.safetensors` (UNet-only) | **5.14 GB** |
| `sdxl_lightning_8step_unet.safetensors` (UNet-only) | **5.14 GB** |
| `sdxl_lightning_2step_lora.safetensors` | 393,854,592 bytes ≈ **394 MB** |
| `sdxl_lightning_4step_lora.safetensors` | **394 MB** |
| `sdxl_lightning_8step_lora.safetensors` | **394 MB** |

### 2.2 Lectura operativa
- **All-in-one:** ~**6.94 GB** por variante. Es el artefacto completo, sin dependencias ocultas.
- **UNet-only:** ~**5.14 GB**, pero **requiere los componentes de SDXL base** (text encoders, VAE, scheduler). Eso significa dependencia oculta sobre el SDXL base canónico.
- **LoRA:** ~**394 MB**, pero **no es un modelo independiente**; necesita una base SDXL ya cargada.

### 2.3 Dependencia oculta
- Si se usa el **all-in-one**, no hay dependencia oculta.
- Si se usa el **UNet-only** o el **LoRA**, sí hay dependencia oculta: se necesita el SDXL base canónico.
- Esto importa para tu criterio de “descargas que tripliquen contenido”.

---

## 3. Versiones INT8 / GGUF más livianas

No hay una versión oficial INT8/FP8 publicada por ByteDance en el repo canónico. Lo que existe son **conversiones GGUF de terceros**.

### 3.1 Mejor opción de terceros: `mzwing/SDXL-Lightning-GGUF`

Este repositorio ofrece variantes **Q4_0, Q4_1, Q5_0, Q5_1 y Q8_0** para los modelos de 1, 2, 4 y 8 pasos.

| Cuantización | Tamaño |
|---|---:|
| **Q4_0** | 2.58 GB |
| **Q4_1** | 2.77 GB |
| **Q5_0** | 2.96 GB |
| **Q5_1** | 3.15 GB |
| **Q8_0** | 4.10 GB |

#### Recomendación concreta
- **Mejor equilibrio calidad/tamaño:** **Q5_0 2.96 GB**  
  - suficiente reducción respecto al all-in-one de 6.94 GB
  - menos pérdida que Q4
- **Opción mínima:** **Q4_0 2.58 GB**  
  - la más liviana
  - mayor riesgo de pérdida de detalle
- **Opción de máxima calidad dentro de GGUF:** **Q8_0 4.10 GB**  
  - más pesada, pero aún mucho menor que el all-in-one

### 3.2 Otra opción: `OlegSkutte/SDXL-Lightning-GGUF`
- Solo publica **Q8_0 4.10 GB** del modelo 4-step.
- Menos flexible que `mzwing`.
- Útil si se quiere exactamente 4-step y se acepta Q8_0.

### 3.3 Nota importante
- `mzwing` es de terceros, pero:
  - usa `stable-diffusion.cpp`,
  - incluye el **fp16 fix VAE** en el paquete,
  - y ha sido referenciado en issues de `stable-diffusion.cpp` como ruta funcional.
- Aun así, **no es oficial de ByteDance**, por lo que:
  - se debe pin el `sha256`,
  - y debe validarse en Stage 2 antes de integrarlo.

---

## 4. Memoria y 720p

- El peso del all-in-one es ~**6.94 GB**, muy similar a SDXL canonical.
- El peso del GGUF Q5_0 baja a ~**2.96 GB**, lo que mejora el margen.
- Aún no hay medición de `load_only` ni `warm_render` en este proyecto.
- El modelo está pensado para **1024×1024**, pero no hay razón estructural para no poder renderizar a `1280×720`; falta medir el pico real.
- **Caveat:** el VAE está incluido en los GGUF de `mzwing`, pero eso no garantiza que el pico de inferencia quepa en 8 GB. Stage 2 sigue siendo obligatorio.

---

## 5. Compatibilidad con LoRAs

- **Fortaleza clara.** SDXL-Lightning es de la familia SDXL, con arquitectura base intacta.
- Los **LoRA checkpoints** de Lightning están diseñados para aplicarse sobre otros SDXL base.
- No hay recorte de capas como en SSD-1B o Vega.
- La compatibilidad estructural con LoRAs SDXL es, en principio, **más directa** que en los modelos destilados con recorte agresivo.
- Aún así:
  - se deben probar las keys,
  - el efecto debe ser visible,
  - y un stack de varios LoRAs puede alterar calidad.

---

## 6. Pros

- **Velocidad extrema:** 1, 2, 4 u 8 pasos.
- **Calidad razonable** en 2/4/8 pasos.
- **Buena compatibilidad con SDXL LoRAs** y con otros checkpoints SDXL.
- **OpenRAIL++-M:** permite uso comercial/publicitario con restricciones de uso aceptable.
- **GGUF de terceros** con tamaños muy reducidos (Q4/Q5/Q8).
- **No requiere refiner** para funcionar.
- **Comunidad grande** (2.2k likes, muchas derivadas y demos).

---

## 7. Contras

- **No es Apache 2.0.**
- **1-step es experimental** y la calidad es inestable.
- **Negative prompt/CFG:**
  - a CFG 1, los negative prompts no tienen efecto,
  - con CFG 2–2.5 hay efecto parcial, pero no tan robusto como en SDXL base.
- **UNet-only y LoRA tienen dependencia oculta** sobre SDXL base.
- **GGUF de terceros** no es oficial, aunque sí funcional.
- **Pico de VRAM no medido** en este host.
- **Calidad de microdetalle** puede ser inferior a SDXL base en configuraciones de pocos pasos.

---

## 8. Descripción como producto

- **Tipo:** acelerador de inferencia dentro de la familia SDXL, no un modelo base nuevo.
- **Uso principal:** generar imágenes en muy pocos pasos cuando el tiempo importa más que la máxima calidad.
- **Perfil ideal:**
  - thumbnails,
  - previews,
  - generación rápida,
  - iteración interactiva,
  - contenido donde la latencia importa.
- **No es ideal para:**
  - máxima fidelidad de microdetalle,
  - negative prompt robusto,
  - flujos que exigen Apache 2.0,
  - escenarios donde no se quiera depender de SDXL base si se usan variantes UNet/LoRA.

---

## 9. Resumen de Stage 2

### Pass si
- se elige un artefacto **all-in-one o GGUF** sin dependencia oculta,
- `load_only` y `warm_render` caben con margen en `1280×720`,
- al menos un LoRA cambia la salida de forma medible,
- un stack de 3 LoRAs no rompe el presupuesto,
- cleanup es limpio,
- y la licencia OpenRAIL++-M se acepta explícitamente.

### Kill si
- el pico de inferencia excede el margen,
- la conversión GGUF introduce inestabilidad,
- la calidad en 4/8 pasos es inferior a la del ancla actual,
- o la dependencia del SDXL base se vuelve una carga oculta no deseada.

---

## 10. Conclusión

- **SDXL-Lightning** es un buen candidato de **velocidad**, no de licencia limpia.
- Si se busca una versión liviana, la mejor ruta es **`mzwing/SDXL-Lightning-GGUF`**, preferiblemente **Q5_0 2.96 GB**.
- Si se busca el mínimo absoluto, **Q4_0 2.58 GB** es la opción más ligera.
- Si se busca máxima calidad dentro de GGUF, **Q8_0 4.10 GB** es la más estable.
- B3 sigue abierto. P10 sigue planned. Stage 2 no se ha ejecutado.

