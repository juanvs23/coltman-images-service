# Hipótesis de la edad: ¿es la generación del modelo la que explica la piel?

> **Purga del 2026-11-19.** El operador ordenó conservar solo `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`. Se borraron **todos** los pesos, renders y logs de candidatos rechazados, y también los de las configuraciones descartadas de MOSS. Lo único que queda en disco es el fichero DMD, sus tres componentes de runtime (VAE FLUX.2, Qwen3.5-9B Q4_K_M, `tokenizer.json`) y los tres renders/logs del DMD. **Las listas de artefactos de este documento son históricas**: describen lo que existió durante la medición, no lo que hay hoy.

**Estado:** hipótesis del operador, comprobada con cuatro modelos del propio proyecto.
**Fecha:** 2026-11-19
**Origen:** el operador sospechó que la piel gomosa de SDXL se debe a la edad del modelo, no a la cuantización.

---

## 1. La hipótesis

> "El problema es la edad de los modelos."

Se probó con los cuatro modelos de los que el proyecto tiene evidencia medida, sobre **el mismo prompt** de grupo de personas (bar, seis jugadores al póker, un barman con delantal, humo, 50 mm).

## 2. Los cuatro puntos

| Modelo | Publicado | Arquitectura | Manos | Piel | Cumple el prompt | Pico | Tiempo |
|---|---|---|---|---|---|---|---|
| **SDXL base** Q8_0 | **2023-07-25** | UNet 2,6B, predicción epsilon | anatomía OK | **gomosa**: sin poros, brillo de silicona | no: 3–5 de 7 personas | 7.170 MiB | 37,1 s |
| **Segmind-Vega** Q8_0 | **2023-11-30** | UNet ~1B, SDXL destilado | **fusionadas** | gomosa | no: 3–5 de 7 | 6.766 MiB | 16,5 s |
| **Z-Image Turbo** fp8 | **2025-11-25** | DiT | **correctas** | **mate, con pliegues, uñas y vello** | **sí**: 6 personas + barman con delantal | ~4.815 MiB | 45,0 s |
| **FLUX.2 [klein] 4B** Q4_K_M | 2026 | DiT, flow matching | correctas | nudillos, tendones, uña, mate | — (ancla actual) | ~4.305 MiB | — |

**La tendencia es monótona con la fecha.** Los dos modelos de 2023 fallan en la superficie de la piel; los dos de 2025–2026 la resuelven. Y no es solo piel: Z-Image es el único que **satisface el prompt completo**, incluido el barman con delantal detrás de una barra de madera, que SDXL y Vega nunca produjeron.

## 3. Lo que "edad" significa mecánicamente

La fecha no causa nada por sí sola. Es un proxy de cinco cambios concretos:

1. **Objetivo de difusión.** SDXL predice epsilon (DDPM); FLUX y Z-Image usan *flow matching* / rectified flow, que converge a detalle de alta frecuencia más limpio y con menos artefactos.
2. **Condicionamiento de texto.** SDXL tiene CLIP-L + CLIP-G (77 tokens). Z-Image lleva un encoder de la familia Qwen3 y FLUX.2 uno de 4B: más comprensión semántica, lo que se ve en el conteo de personas y en los roles.
3. **Datos de entrenamiento.** Los modelos nuevos se entrenaron sobre datos mejor curados, a mayor resolución y con más peso en piel y rostro.
4. **Escala.** UNet de 2,6B en SDXL frente a DiT de 4B en klein.
5. **VAE.** El VAE de SDXL es conocido por ser blando; los VAE posteriores conservan más microdetalle.

**Conclusión mecánica:** la piel gomosa es el techo de calidad de superficie de la generación 2023, no un defecto del fichero, de la cuantización, de los pasos ni del CFG — los cuatro se descartaron con medición en `p10-b3-sdxl-canonical-stage2-report.md` §4.1.

## 4. Qué fue descartado antes de llegar aquí

- **Cuantización**: el bf16 de SDXL, con cero tensores cuantizados, da la misma piel o peor.
- **Pasos**: 50 en vez de 30 no la mejora y funde las fichas.
- **CFG**: CFG 5 no la mejora y añade textura falsa al cuero de la mesa.
- **Resolución**: Z-Image rinde a 1280×720 (921.600 px), menos píxeles que los 1024² de SDXL (1.048.576 px), y aun así gana en superficie. Más píxeles no arreglarían a SDXL.

## 5. La consecuencia incómoda

**Z-Image Turbo ya está instalado en el proyecto**, corre a ~4.815 MiB y resuelve esta escena mejor que cualquier candidato del campo B3 probado hasta ahora — con menos memoria que SDXL, Vega o klein.

Eso cambia la pregunta de B3. Si el objetivo es "un modelo que haga personas bien", **el proyecto ya lo tiene**. Si el objetivo es otra cosa — cobertura de LoRA, otra estética, otro régimen de pasos — entonces el campo de candidatos debe evaluarse contra ese otro criterio, no contra calidad de piel, donde los modelos de 2023 no pueden competir.

## 6. Qué queda por comprobar

- **MOSS-Image (C9)** es de la generación 2025 y Apache 2.0. Si la edad manda, es el candidato del campo con más probabilidad de piel correcta. Su problema es otro: encoder Qwen3.5 de 9B y ~15,4 GB operativos. **Es el único del campo que sigue teniendo sentido probar por calidad.**
- **SDXL Q4_K (C3B)** ya no tiene justificación por calidad: si Q8_0 y bf16 fallan en piel, Q4_K no la va a arreglar, solo abaratar memoria.
- **LoRA de detalle sobre SDXL**: la única vía conocida para que un modelo de 2023 cierre la brecha de superficie. Es exactamente lo que el gate L1/L2/L3 mediría, y sigue abierto.

## 7. Evidencia

Bajo `run/`, excluido por el ignore file:

- `p10-stage2/zimage-poker-seed7.png` — Z-Image, mismo prompt, seed 7, 1280×720, 12 pasos
- `p10-stage2/zimage-hands-4x.png` — manos de Z-Image a 4×: pliegues, uñas, vello
- `p10-stage2/sdxl-canonical/hands-3x-contact.png` — manos de SDXL a 3× (tres seeds)
- `p10-stage2/sdxl-canonical/skin-sweep-3x.png` — 30 vs 50 pasos vs CFG 5
- `p10-stage2/sdxl-canonical/ab-q8-vs-bf16-3x.png` — el A/B que exonera la cuantización
- `p10-stage2/sdxl-canonical/ab-three-models-3x.png` — SDXL Q8_0, SDXL bf16 y FLUX klein
- `tests/e2e/flux2-klein/evidence/poker-realistic.png` — el ancla, mismo prompt

**Nota:** las resoluciones no son idénticas (1280×720 para Z-Image, 1024² para SDXL) porque cada modelo se midió en su configuración declarada. El juicio de piel se hace a 3–4× sobre el recorte, y no depende de esa diferencia.
