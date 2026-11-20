# DreamShaper XL (Lightning y v2) y MOSS-Image — Stage 2 medido

> **Purga del 2026-11-19.** El operador ordenó conservar solo `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`. Se borraron **todos** los pesos, renders y logs de candidatos rechazados, y también los de las configuraciones descartadas de MOSS. Lo único que queda en disco es el fichero DMD, sus tres componentes de runtime (VAE FLUX.2, Qwen3.5-9B Q4_K_M, `tokenizer.json`) y los tres renders/logs del DMD. **Las listas de artefactos de este documento son históricas**: describen lo que existió durante la medición, no lo que hay hoy.

**Estado:** tres candidatos medidos con el mismo prompt. **MOSS-Image es el único que cumple el prompt entero.**
**Fecha:** 2026-11-19
**Runtime:** `sd.cpp` `532d2c1`, `sd-cli`
**Relacionados:** `p10-b3-model-age-hypothesis.md`, `p10-b3-sdxl-canonical-stage2-report.md`, ledger §19

---

## 0. Nota de reversión

La familia **DreamShaper XL** fue eliminada del campo el 2026-11-18 **por instrucción del operador** (ledger §12). El 2026-11-19 el operador la reincorporó parcialmente pidiendo **Lightning** y **v2**. Se registra como reversión de su propia decisión, no como rehabilitación técnica. Con la evidencia de este informe, la reincorporación se justifica como comparación, no como candidata: los dos DreamShaper conservan el techo de 2023.

## 1. Artefactos y verificación

Los seis ficheros se bajaron por nombre exacto, con reanudación `curl -C -`, y se verificaron contra su LFS SHA-256 en `run/p10-stage2/verify.sh` — **los seis pasan**.

| Componente | Repo | Bytes | SHA-256 |
|---|---|---:|---|
| DreamShaper Lightning | `Lykon/dreamshaper-xl-lightning` | 6.939.220.250 | `fdbe5635…4f64` |
| DreamShaper v2 (Turbo) | `Lykon/dreamshaper-xl-v2-turbo` | 6.939.220.250 | `4726d3ba…1c67` |
| MOSS-Image SFT DiT Q4_K | `leejet/MOSS-Image-SFT-GGUF` | 3.327.400.800 | `902dbb03…2225` |
| MOSS LLM Qwen3.5-9B Q4_K_M | `unsloth/Qwen3.5-9B-GGUF` | 5.680.522.464 | `03b74727…b7e8` |
| MOSS VAE FLUX.2 | `Comfy-Org/MOSS-Image` | 336.211.292 | `868fe7b3…e8f3` |
| MOSS tokenizer | `OpenMOSS-Team/MOSS-Image-Base` | 19.989.325 | `06b95093…e523` |

**Los dos DreamShaper son checkpoints completos** (UNet + ambos CLIP + VAE) y cargan con `-m`.
**MOSS son cuatro componentes** y requiere la receta del doc del runtime: `--diffusion-model`, `--llm`, `--vae`, `--tokenizer` externo obligatorio (Qwen3.5 usa vocabulario distinto del Qwen embebido).

## 2. Mediciones

Mismo prompt de grupo de personas, seed 7, 1024×1024, `--offload-to-cpu`. Tarjeta de 8.188 MiB, línea base 295 MiB.

| Modelo | Config | exit | Tiempo | Pico | Libre | Render |
|---|---|---:|---:|---:|---:|---|
| DreamShaper Lightning | 6 pasos, CFG 2 | 0 | 24,7 s | 5.922 MiB | 2.266 MiB | 1024×1024 |
| DreamShaper v2 Turbo | 8 pasos, CFG 2 | 0 | 27,0 s | 5.922 MiB | 2.266 MiB | 1024×1024 |
| **MOSS-Image SFT** | **CFG 3, 20 pasos (default)** | 0 | **102,5 s** | **4.294 MiB** | **3.894 MiB** | 1024×1024 |

**MOSS es el que menos VRAM consume de todos los probados**, y con diferencia: 4.294 MiB frente a 5.922 de los DreamShaper y 7.170 de SDXL residente.

### 2.1 Por qué MOSS gasta menos

Del log del propio runtime:

| Modelo | Pesos (en RAM, offload) | Buffer DiT/UNet | Buffer VAE |
|---|---|---|---|
| DreamShaper Lightning | 6.624 MB (UNet 4.900 fp16) | 492 MiB | **3.840 MiB** |
| MOSS-Image SFT | 7.946 MB (DiT 3.174 Q4_K) | 596 MiB | **FLUX.2, mucho menor** |

La diferencia no está en los pesos: **está en el VAE**. SDXL arrastra el suyo, cuyo decoder pide 3.840 MiB a 1024². MOSS usa el VAE de FLUX.2, mucho más eficiente. Es el tercer modelo que confirma que **el muro de memoria de la familia SDXL es su VAE**, no el UNet.

## 3. Calidad

### 3.1 MOSS-Image SFT

**Es el único que cumple el prompt completo.** Siete personas sentadas a la mesa **más el barman de camisa blanca y delantal negro apoyado en la barra de madera**, con botellas y cristalería detrás. Humo saliendo en columna. Copas con agua, fichas apiladas, cartas con palos legibles.

La piel es la mejor de todo el campo: **arrugas de expresión, barba de varios días, pelo individual, matte real**. Los rostros tienen edad y carácter en vez de ser maniquíes. Las manos se leen como manos. La profundidad de campo aparece de verdad, con bokeh.

Se parece a un fotograma de cine, no a una generación.

### 3.2 DreamShaper XL Lightning

- **Mejora las caras** respecto a SDXL base: estructura facial más definida.
- **Manos: siguen mal.** La mano izquierda que sostiene la copa es una garra; la derecha, un bulto; las del centro, apenas formadas. Piel gomosa.
- **Cuatro personas**, no siete. **No hay barman tras la barra**: el delantal aparece en un jugador sentado.
- Mesa vacía, pocas fichas, cartas en un montón.

### 3.3 DreamShaper XL v2 Turbo

- Caras algo mejores que Lightning, con el hombre central bien resuelto.
- **Manos: garras y dedos fundidos** en las cuatro visibles.
- **Cuatro personas enfocadas** más figuras borrosas al fondo. **No hay barman tras la barra**; el delantal se lo pone la mujer.
- **Colapso de vestuario**: todos con camisa blanca y chaleco o delantal, tomado del rol de barman.

### 3.4 El patrón

Los dos DreamShaper son **fine-tunes de SDXL de 2024**. Suben la calidad de cara y de iluminación, que es lo que un fine-tune arregla, y **no tocan el techo estructural de 2023**: manos, conteo de sujetos, coherencia de roles y piel. Confirman la hipótesis de la edad por la vía negativa: mejorar el modelo base de 2023 no lo saca de 2023.

## 4. Tabla completa del campo probado

| Modelo | Fecha | Pico | Tiempo | Personas (7 pedidas) | Manos | Piel | Barman tras barra |
|---|---|---:|---:|---|---|---|---|
| SDXL base Q8_0 | 2023-07 | 7.170 | 37,1 s | 3–5 | anatomía OK | gomosa | no |
| Segmind-Vega Q8_0 | 2023-11 | 6.766 | 16,5 s | 3–5 | fusionadas | gomosa | no |
| DSXL Lightning | 2024-02 | 5.922 | 24,7 s | 4 | garras | gomosa | no |
| DSXL v2 Turbo | 2024-02 | 5.922 | 27,0 s | 4 | garras | mixta | no |
| Z-Image Turbo | 2025-11 | ~4.815 | 45,0 s | 6 + barman | correctas | mate, pliegues | **sí** |
| **MOSS-Image SFT** | **2026-10** | **4.294** | **102,5 s** | **7 + barman** | **correctas** | **arrugas, barba, poros** | **sí** |

## 5. Veredicto

**MOSS-Image SFT gana en calidad y gana en VRAM.** Es el único que satisface el prompt entero, el único con piel que aguanta una ampliación, y el que menos memoria pide: 4.294 MiB, por debajo de Z-Image (4.815), de klein (4.305) y muy por debajo de SDXL (7.170).

**El precio es el tiempo: 102,5 s por imagen.** Cuatro veces SDXL, 2,3 veces Z-Image. La causa es el encoder Qwen3.5-9B: 4.611 MB que se transmiten desde RAM en cada prompt.

**DreamShaper queda descartado como candidato** por la evidencia: dos fine-tunes de SDXL que no arreglan lo que SDXL no hace. Se conservan como referencia medida.

## 6. Lo que queda por hacer

- **Gate de LoRA sobre MOSS.** Es el único con sentido ahora. `MOSS-Image Base` es la variante pensada para entrenar LoRA y existe `mossloras/moss-image-lora-archive`. L1/L2/L3 siguen sin ejecutarse en ningún candidato.
- **Reducir el tiempo de MOSS**: probar el LLM en Q3_K_XL o IQ4_XS (5,17 GB frente a 5,68), y medir si el paso por CPU del encoder domina el coste.
- **Decisión de producto**: 102 s por imagen, ¿es aceptable? Es la única pregunta que hoy separa a MOSS de ser el modelo del proyecto.

## 7. Artefactos

Bajo `run/p10-stage2/`, excluido por el ignore file:

- `dreamshaper-lightning/render-dsxl-lightning-1024-s7-6st-cfg2.png` + log
- `dreamshaper-v2/render-dsxl-v2-1024-s7-8st-cfg2.png` + log
- `moss-image/render-moss-sft-1024-s7.png` + log
- `MANIFEST.md` — los seis artefactos pinneados
- `fetch.sh` + `verify.sh` — descarga idempotente y verificación de digests
- `probe.py` — probe común (soporta componentes separados con `--vae/--llm/--tokenizer`)

## 8. Segunda ronda sobre MOSS: menos pasos, cuantización y VAE diminuto

El operador pidió tres cosas sobre MOSS: buscar una versión cuantizada, probar con menos pasos y buscar un VAE cuantizado. Los DreamShaper se borraron por su instrucción; sus renders y logs se conservan.

### 8.1 Dónde se va el tiempo

Desglose del log del propio runtime, a 20 pasos:

| Fase | Tiempo |
|---|---|
| Carga de pesos (DiT + encoder) | 15,3 s |
| Grafo de condicionamiento (Qwen3.5-9B) | **10,8 s** |
| **Sampling** | **88,0 s** — 4,05 s/paso |
| Decoder del VAE | **2,14 s** |

La ecuación del modelo es `steps × 4,05 s + ~15 s`. **El muestreo es el 86% del tiempo; el VAE, el 2%.**

### 8.2 Menos pasos — la palanca real

| Pasos | Tiempo | Pico medido | Calidad |
|---:|---:|---:|---|
| 20 (default) | 102,5 s | 4.294 MiB | siete personas + barman, piel real |
| 12 | 68,8 s | 5.030 MiB | intermedia |
| **8** | **52,8 s** | 5.062 MiB | **aguanta**: siete personas + barman con delantal, piel y manos utilizables |

**Bajar de 20 a 8 pasos reduce el tiempo a la mitad sin colapso de calidad en este prompt.** Es la única palanca que mueve la aguja.

**Anomalía declarada:** el pico sube con menos pasos (4.294 → 5.062 MiB). El delta frente a la línea base pasa de 3.999 a 4.755 MiB. No hay explicación establecida; el runtime reutiliza búferes de forma distinta y no se ha instrumentado. Se registra como observación, no como causa.

### 8.3 Versión cuantizada

Ya se ejecuta **Q4_K (3,33 GB)**, que es la cuantización sana más pequeña: existen Q3_K (2,70 GB) y Q2_K (2,21 GB), pero **no compran tiempo** — el sampling es 4,05 s/paso con independencia del ancho del peso — y la RAM no es la restricción (22 GB libres). Bajar más solo degrada.

La vía que sí cambia algo es un **destilado DMD a 8 pasos**:

- `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot` — **un solo fichero** de 5.413.723.302 B (`sha256 df80b9fe…b0f4`). int8 es un formato que `sd.cpp` soporta (`docs/guides/int8_convrot.md`) y el DMD va horneado en los pesos, así que 8 pasos son su régimen nativo y no una concesión.
- `lodestones/MOSS-Image-SFT-8-steps-dmd` — shards diffusers + `lora.safetensors` (1,19 GB), no es un single-file.

### 8.4 VAE diminuto (la petición del "VAE cuantizado")

Existe un TAE para FLUX.2: `AcademiaSD/TAE_Flux2_AcademiaSD` → `TAE_Flux2_AcademiaSD.safetensors`, **3.333.534 B** (frente a los 336.211.292 B del VAE completo).

**No carga en este build.** Con `--taesd` el runtime falla con:

```
[E] VAE tensor 'tae.encoder.layers.9.conv.0.weight' not in model metadata
```

El cargador de TAE de `sd.cpp` espera otra estructura de tensores que la que publica ese repo. Exit 1, sin imagen, 0,9 s.

**Y aunque cargara, no aportaría:** el decode del VAE son 2,14 s de 102,5 s. Sustituirlo por un autoencoder 100 veces más pequeño ahorraría, en el mejor caso, dos segundos.

### 8.5 Conclusión de la segunda ronda

- **Menos pasos: sí, y ya está medido.** 8 pasos, 52,8 s, calidad utilizable.
- **VAE cuantizado: no.** No carga, y su techo de ahorro son 2 s.
- **Cuantización del DiT: ya aplicada (Q4_K).** Más agresiva no acelera.
- **Lo único que quedaría por probar** es el DMD int8 de 8 pasos (5,41 GB), si se quiere que 8 pasos sea el régimen nativo del modelo en vez de una concesión sobre uno de 20.

## 9. DMD int8 a 8 pasos — el cierre del campo

Última pieza: `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`, un **single-file** de 5.413.723.302 B, SHA-256 `df80b9fe08f6118c76adac33b00229ece3953200be9bccedf0371bace04eb0f4` (**verificado localmente**), en formato int8-convrot que `sd.cpp` soporta y con la destilación DMD horneada en los pesos. Se carga como `--diffusion-model` con los mismos tres componentes.

### 9.1 Mediciones

Mismo prompt, seed 7, 1024×1024, `--offload-to-cpu`, CFG 3,0.

| Configuración | Pasos | Tiempo | Pico | Libre |
|---|---:|---:|---:|---:|
| Q4_K (no destilado) | 20 | 102,5 s | 4.294 MiB | 3.894 MiB |
| Q4_K (no destilado) | 12 | 68,8 s | 5.030 MiB | 3.158 MiB |
| Q4_K (no destilado) | 8 | 52,8 s | **5.062 MiB** | 3.126 MiB |
| **DMD int8** | 8 | **47,6 s** | 5.994 MiB | 2.194 MiB |
| DMD int8 | 6 | 37,8 s | 5.994 MiB | 2.194 MiB |
| DMD int8 | 4 | **34,3 s** | 5.994 MiB | 2.194 MiB |

El pico del DMD es constante en 5.994 MiB con independencia de los pasos: **lo fija el ancho del peso, no el muestreo**. Int8 ocupa más que Q4_K y por eso pide ~930 MiB más.

### 9.2 Calidad

- **8 pasos (47,6 s):** la mejor imagen del campo junto a la de 20 pasos. Seis jugadores más el **barman de camisa blanca y delantal negro tras la barra**, sirviendo con un paño azul. Piel con barba, arrugas y variación de edad; manos con dedos y uñas; botellas, copas y cartas legibles; fondo con parroquianos desenfocados. Es su régimen nativo: el DMD está destilado para 8 pasos, así que aquí no hay concesión.
- **6 pasos (37,8 s):** intermedia, sin defectos nuevos.
- **4 pasos (34,3 s):** **aguanta**. Seis jugadores y el barman siguen ahí, con piel y caras utilizables; algo más suave en sombras y en el detalle fino de manos y cristal, y con las manos del primer plano algo menos definidas. Utilizable, no óptimo.

### 9.3 El intercambio final

| Quiero… | Configuración | Coste |
|---|---|---|
| Máxima calidad | DMD int8, 8 pasos | 47,6 s · 5.994 MiB |
| Máxima velocidad | DMD int8, 4 pasos | **34,3 s** · 5.994 MiB |
| Máxima holgura de VRAM | Q4_K, 8 pasos | 52,8 s · **5.062 MiB** |

**DMD a 8 pasos es el punto de equilibrio**: 47,6 s, apenas 2,6 s más que Z-Image (45,0 s), con adherencia al prompt y piel muy superiores. **A 4 pasos es el más rápido de todo el campo con calidad utilizable.**

### 9.4 Margen para LoRA

Con DMD la VRAM libre en el pico es **2.194 MiB**, por debajo del presupuesto declarado de 3.200 MiB. Con Q4_K a 8 pasos son 3.126 MiB, también por debajo. **Ninguna configuración de MOSS cumple el presupuesto de LoRA en el papel**, y como en el resto del campo la cuenta es una cota: con offload los pesos viven en RAM y un LoRA fusionado puede costar RAM. Sigue decidiéndolo L1/L2/L3, que no se ha ejecutado.

## 10. Cierre del campo

Con esto queda medido todo lo que el campo tenía que medir. El resultado, en una línea: **MOSS-Image SFT es el único modelo que cumple el prompt completo, el que mejor rinde la piel, y el único que además baja de 50 s sin degradarse** — a costa de picos de memoria más altos que Q4_K y de un encoder de 9B que domina el tiempo de condicionamiento.

## 11. Gate de LoRA sobre el DMD — L1 y L2 ejecutados

Primer LoRA real sobre el modelo que sobrevive: `axiomofmind/Moss-image-anime-lora-GGUF` → `MOSS-Image-Anime-LoRA-F16.gguf`, **74.365.536 B**, SHA-256 `AC90C81F9463E64CF9BE0AA87FEE00C2315DBF2AF089EF62725FEDB58E8F6989` (**verificado**). Rank 16, alpha 16, GGUF F16, **504 tensores LoRA** según el autor. Se carga con `--lora-model-dir` y la etiqueta `<lora:MOSS-Image-Anime-LoRA-F16:1.0>` en el prompt, con `--lora-apply-mode at_runtime`.

Prompt del propio README del LoRA —escena de acción con `anime character`, que es el dominio para el que fue entrenado—, seed 7, 1024×1024, 8 pasos, CFG 3,0, offload. **Las dos corridas usan el prompt idéntico**; la única diferencia es la etiqueta.

### L1 — mapeo de claves: pasa

```
[I] apply lora at runtime --- diffusion_engine.cpp:1749
[I] (504 / 504) LoRA tensors have been applied, lora_file_path = .../MOSS-Image-Anime-LoRA-F16.gguf --- lora.hpp:1054
```

**504 de 504, cero tensores descartados.** Es la comprobación que el proyecto exige y precisamente la que falló con FLUX.2 [klein], donde un LoRA cargó, imprimió `apply lora at runtime` y **descartó 86 de 172 tensores en silencio** hasta que se parcheó el conversor. En MOSS el conversor (`convert_moss_image_dit_name`, más el bloque Qwen3.5) mapea limpio.

### L2 — efecto no nulo: pasa

| Corrida | Tiempo | Pico |
|---|---:|---:|
| A — sin LoRA | 41,9 s | 6.004 MiB |
| B — con LoRA (1.0) | 60,6 s | 6.592 MiB |

**Diferencia media entre A y B: 50,35 / 255**, máximo 255, **1.047.420 de 1.048.576 píxeles distintos**. La referencia del proyecto: 4,8/255 era "nada" y 40,2/255 era "efecto real". **50,35 está por encima del umbral con margen.**

Y no es ruido: es el estilo que el LoRA declara. A sale como ilustración anime de sombreado suave; B sale en **cel-shading con línea negra dura, encuadre diagonal bajo y composición de acción** — exactamente el "seinen de acción, luz cinematográfica, siluetas fuertes" que describe su card. El rayo azul de A desaparece en B: la composición cambia, no solo el filtro.

### Coste real de aplicar un LoRA

| | Sin LoRA | Con LoRA | Δ |
|---|---:|---:|---:|
| Tiempo | 41,9 s | 60,6 s | **+18,7 s (+45%)** |
| Pico | 6.004 MiB | 6.592 MiB | **+588 MiB** |

**Con un solo LoRA el pico sube a 6.592 MiB, dejando 1.596 MiB libres** — muy por debajo de los 3.200 MiB que declara `host.yaml`. El coste de `at_runtime` no es despreciable ni en tiempo ni en memoria.

### L3 — pendiente

Falta apilar **tres LoRAs distintos** y verificar que los tres aplican. No hay un segundo y tercer LoRA en disco: harían falta dos descargas de ~74 MB cada una (`Moss-image-beauty-lora-GGUF`, `Moss-image-psychedelic-lora-GGUF` u otros del mismo autor).

### Lo que este gate NO cubre

- Los LoRAs publicados están entrenados y validados sobre **MOSS-Image SFT**, no sobre el **DMD destilado**. Aun así L1 y L2 pasan, lo que indica que la destilación no rompió los objetivos del adaptador. **Falta una comprobación de calidad**: no hay render de control del mismo LoRA sobre SFT, así que no se puede afirmar que el efecto sobre el DMD sea idéntico al que documenta el autor.
- El presupuesto de memoria no se cumple con un LoRA. Con tres, menos.

## 12. LoRAs de rendimiento — uno descartado por incompatibilidad, otro adoptado

El operador fijó **8 pasos** como estándar tras ver que el DMD a 4 pasos se afea, y pidió probar los adaptadores de velocidad.

### 12.1 `Epyan/MOSS-Image_4-step_adapter_lora` — descartado sin descargar

Es el más prometedor sobre el papel: 4 pasos **sin CFG**, y **continúa desde `lodestones/MOSS-Image-SFT-8-steps-dmd`**, que es exactamente nuestro punto de partida. Pero su propio README (en japonés) lo descalifica para este runtime:

- **`time_embedding.safetensors`** reemplaza `time_embedding.*`, `shared_block_modulation.bias` y `video_head_modulation.bias`. Dice literalmente: *"aplicar solo el LoRA no funciona correctamente"* — el vector de tiempo de `t=1` está plegado en el bias, y los tres módulos van en conjunto.
- **Sampler propio**: `x = z + Q·x0`, `x0 = z − v`, repetido 4 veces, con `step_codes` como timesteps y un `dataspace.safetensors` que aporta la matriz `Q`.
- **Excluye los loaders de tipo merge** de forma explícita — nombra `LoraLoaderModelOnly` de ComfyUI y `fuse_lora` de diffusers como caminos que no sirven.

`sd.cpp` no implementa ese sampler ni permite sustituir el time embedding. **Descartado por incompatibilidad de runtime, no por calidad.** Los 1,2 GB no se descargaron en esta ronda — **corregido después: sí se descargaron y se midieron, ver §14.4, donde la predicción de "basura" resultó equivocada.**

### 12.2 `anyMODE/moss-image-12step-turbo-lora` — adoptado

LoRA plano, rank 64, pensado para **CFG 1.0**, con proyección CFG-Zero* para evitar el quemado de contraste. Fichero `12_step_turbo_moss_1024_distill_v8_r64_weightsx2.safetensors`, **284.147.832 B**, SHA-256 `873f6de07cf21ae3a373c009383da3d120092a8f3a0ba92c9dc5815693ca24df` (**verificado**).

**L1: `(552 / 552) LoRA tensors have been applied`** — cero descartados.

| Configuración | Pasos | CFG | Tiempo | Pico | σ luminancia |
|---|---:|---:|---:|---:|---:|
| DMD solo (baseline) | 8 | 3,0 | 47,6 s | **5.994 MiB** | 57,53 |
| **DMD + turbo LoRA** | **8** | **1,0** | **40,4 s** | 6.686 MiB | **60,40** |
| DMD + turbo LoRA | 12 | 1,0 | 49,7 s | 6.686 MiB | — |

**A 8 pasos gana 7,2 s (−15%) con calidad igual o mejor.** La razón es estructural: con CFG 1,0 no hay rama negativa, así que cada paso cuesta una pasada en vez de dos. A 12 pasos pierde el sentido: tarda más que el baseline de 8.

Diferencia media contra el baseline: **31,90/255** — imágenes distintas, como corresponde a otro camino de muestreo, no ruido. El contraste sube ligeramente (σ 57,53 → 60,40), coherente con lo que el adaptador promete.

**Coste:** +692 MiB de pico (5.994 → 6.686), dejando **1.502 MiB libres**.

### 12.3 Configuración recomendada

**DMD int8 · 8 pasos · CFG 1,0 · turbo LoRA a 1.0 → 40,4 s.** Es más rápida que Z-Image (45,0 s) con mejor adherencia al prompt y mejor piel.

Si en algún momento se necesita holgura de VRAM por encima de todo, el baseline sin LoRA a 8 pasos y CFG 3,0 da 47,6 s con 692 MiB menos de pico.

## 13. KV-cache: el LoRA no aplica, y el caché del runtime no compensa a 8 pasos

El operador preguntó por `p1atdev/MOSS-Image-SFT-KV-Cache-LoRA`. Se investigaron las dos vías posibles y **ambas se cierran**, por motivos distintos.

### 13.1 El LoRA es una corrección, no un acelerador

Su README lo dice literal: *"an experimental correction LoRA for fixed-timestep text KV caching"* y **"the adapter alone does not enable caching"**. El mecanismo —calcular una vez las K/V de la atención de texto y reutilizarlas durante el denoising— lo implementa un **nodo de ComfyUI** (`comfy-moss-image-kv-cache`, con `text_timestep` 1000); el LoRA solo compensa el error que esa aproximación introduce.

`sd.cpp` **no implementa esa aproximación**. Por tanto el adaptador no tiene nada que corregir: aplicarlo a ciegas inyectaría una corrección para un error que no estamos cometiendo. **En esta ronda no se descargó — corregido después: se descargó y se midió en §14.3, y la medición confirma el razonamiento (+58% de tiempo y peor imagen).**

### 13.2 El objetivo sí existe en el runtime, pero no a 8 pasos

`sd.cpp` trae `--cache-mode` con estrategias para DiT: `dbcache` (umbral de residuo L1 por bloque), `taylorseer`, `cache-dit`, `easycache`. Es el mismo objetivo por otro mecanismo, y se midió sobre la configuración recomendada (8 pasos, CFG 1,0, turbo LoRA):

| Configuración | Tiempo | Resultado |
|---|---:|---|
| Sin caché | **40,4 s** | referencia |
| `dbcache` (threshold 0,25, warmup 4) | 41,1 s | **más lento** |
| `cache-dit` | 42,0 s | **más lento** |
| `dbcache` agresivo (threshold 0,5, warmup 1) | **38,7 s** | −1,75 s, **pero degrada** |

El agresivo oscurece y aplana la imagen: luminancia media **49,22 → 40,42** y desvío **60,40 → 50,58**, con diferencia media de **23,03/255**. Un 4% de tiempo a cambio de contraste y detalle visibles.

**Por qué no funciona aquí:** el caché compensa a partir de muchos pasos, cuando los estados entre iteraciones cambian poco. A 8 pasos apenas hay nada que reutilizar, y el `warmup` se come buena parte del presupuesto.

### 13.3 Conclusión

**El KV-cache es un callejón sin salida para este despliegue, por las dos puertas.** El LoRA no aplica porque el runtime no tiene el mecanismo; el mecanismo equivalente del runtime no paga a 8 pasos.

La configuración recomendada no cambia: **DMD int8 · 8 pasos · CFG 1,0 · turbo LoRA → 40,4 s**, que ya es más rápida que Z-Image con mejor calidad.

## 14. Segunda pasada: el catálogo de LoRAs medido, y dos correcciones a mí mismo

El operador pidió bajar el resto del catálogo y preguntó si había probado el LoRA de caché. **No lo había probado: lo descarté por razonamiento.** Esta sección corrige eso con medición, incluida una predicción mía que resultó equivocada.

### 14.1 Catálogo descargado y verificado

| LoRA | Fichero | Bytes |
|---|---|---:|
| Anime (seinen) | `MOSS-Image-Anime-LoRA-F16.gguf` | 74.365.536 |
| Beauty | `MOSS-Image-Beauty-LoRA-F16.gguf` | 74.365.536 |
| Gouache | `MOSS-Image-Gouache-LoRA-F16.gguf` | 74.365.536 |
| Psychedelic | `MOSS-Image-Psychedelic-LoRA-F16.gguf` | 74.365.536 |
| Pose control | `moss_image_sft_pose_control_lora.safetensors` | 290.254.336 |
| Depth control | `moss_image_sft_depth_control_lora.safetensors` | 290.254.336 |
| Editing | `moss_edit_lora_poc.safetensors` | 297.328.736 |
| Manga (alpha) | `moss_manga_alpha_image_lora.safetensors` | 132.162.296 |
| KV-cache v2 | `moss_image_sft_kv_cache_v2_step000500.safetensors` | 148.726.512 |
| 4-step adapter (Epyan) | `epyan_4step_lora.safetensors` | 1.189.176.832 |
| 12-step turbo | `12_step_turbo_moss_1024_distill_v8_r64_weightsx2.safetensors` | 284.147.832 |

2,8 GB en total. Todos los tamaños coinciden con lo publicado.

### 14.2 L3 — tres LoRAs apilados: PASA

Anime + Beauty + Gouache en un mismo prompt, 8 pasos, CFG 1,0:

```
(504 / 504) LoRA tensors have been applied  → Anime
(504 / 504) LoRA tensors have been applied  → Beauty
(504 / 504) LoRA tensors have been applied  → Gouache
```

**Los tres aplican completos, cero tensores descartados.** 60,6 s y 7.086 MiB de pico (1.102 MiB libres). La imagen cambia 43,95/255 respecto al turbo solo y baja el contraste (σ 60,40 → 47,80), que es lo esperable al mezclar tres estilos.

**L3 mide mecanismo, no estética:** el apilado de tres estilos sobre un prompt fotográfico no se juzga visualmente porque no es un caso de uso, es una prueba de que el runtime aplica varios adaptadores a la vez sin perder ninguno.

### 14.3 KV-cache — probado y descartado por medición

`moss_image_sft_kv_cache_v2_step000500.safetensors` junto al turbo, 8 pasos, CFG 1,0:

| | Turbo solo | Turbo + KV-cache |
|---|---:|---:|
| Tiempo | **40,4 s** | **63,9 s** |
| Pico | 6.686 MiB | 6.828 MiB |
| σ luminancia | 60,40 | 59,18 |
| Tensores | 552/552 | 552/552 + **756/756** |

**Aplica completo y empeora las dos cosas:** un **58% más de tiempo** y una imagen más plana (diferencia 34,79/255, σ 60,4 → 59,2). Confirma lo que el README decía —es una corrección para un error que este runtime no comete— pero ahora **medido, no argumentado**.

### 14.4 El adaptador de 4 pasos — mi predicción era errónea

Escribí en §12.1 que, sin su sampler, produciría basura. **No es así.** A 4 pasos y CFG 1,0 con la etiqueta puesta:

- `(756 / 756) LoRA tensors have been applied`
- **42,3 s**, pico **7.308 MiB**
- Imagen **usable**: seis jugadores más el barman tras la barra, coherente

Pero es **más blando** que el turbo a 8 pasos (σ 54,35 frente a 60,40; caras y manos menos definidas) y **más lento** (42,3 s frente a 40,4 s), con 622 MiB más de pico.

**La conclusión no cambia —no se usa— pero el motivo sí:** no es que "no funcione", es que **no gana nada** y cuesta más en las tres monedas. La incompatibilidad de su sampler sigue siendo real para obtener su régimen completo, pero su aplicación parcial no revienta.

### 14.5 Configuración final, sin cambios

**DMD int8 · 8 pasos · CFG 1,0 · turbo LoRA a 1.0 → 40,4 s.** Ninguno de los nueve adaptadores restantes la mejora.

## 15. Corrección: 12 pasos sí compensa, y el turbo casi no ayuda ahí

Dos correcciones al cierre anterior, ambas planteadas por el operador.

### 15.1 El LoRA de caché, borrado, y sin sustituto

`moss_image_sft_kv_cache_v2_step000500.safetensors` **eliminado**. No hay reemplazo apropiado que buscar: el bloqueo no está en el adaptador, está en el runtime. `sd.cpp` no implementa caché de K/V de texto, así que **cualquier LoRA de corrección para ese mecanismo carece de objeto**. Buscar otro sería repetir el mismo error con otro fichero.

### 15.2 Los 12 pasos: mi descarte fue perezoso

En §12.2 escribí que 12 pasos "pierde el sentido: tarda más que el baseline de 8". **Comparé tiempo contra tiempo y nunca miré la imagen de 12 pasos.** Vista, es **mejor**: caras y manos más definidas, botellas del fondo más nítidas, más contraste (σ 61,18 frente a 60,40). El operador tenía razón.

### 15.3 La comparación completa, que faltaba

| Configuración | Pasos | CFG | Tiempo | Pico | σ luminancia |
|---|---:|---:|---:|---:|---:|
| DMD solo | 4 | 3,0 | 34,3 s | 5.994 MiB | — |
| DMD solo | 6 | 3,0 | 37,8 s | 5.994 MiB | — |
| DMD solo | 8 | 3,0 | 47,6 s | 5.994 MiB | 57,53 |
| **turbo LoRA** | 8 | 1,0 | **40,4 s** | 6.686 MiB | 60,40 |
| **turbo LoRA** | 12 | 1,0 | 49,7 s | 6.686 MiB | 61,18 |
| **sin LoRA** | **12** | **3,0** | 52,2 s | **6.394 MiB** | **63,24** |

**El turbo a 12 pasos ahorra solo 2,5 s** (49,7 frente a 52,2) y cuesta 292 MiB más de pico y algo de contraste. A 8 pasos ahorraba 7,2 s. La razón es que el coste fijo domina: **cargar los pesos (≈15 s) más el encoder Qwen3.5 (≈11 s) son ~26 s que no dependen de los pasos**; con 12 pasos, el margen que el CFG 1,0 puede recortar es menor en proporción.

### 15.4 Consecuencia: la decisión es de pasos, no de LoRA

- **Máxima calidad**: 12 pasos **sin LoRA** → 52,2 s, **6.394 MiB** (el pico más bajo de las tres), σ 63,24.
- **Máxima velocidad**: 8 pasos con turbo → 40,4 s, 6.686 MiB.
- **12 pasos con turbo** queda en tierra de nadie: 2,5 s de ventaja por 292 MiB y menos contraste.

**Queda por decidir del operador, no por medir:** si 9 s de diferencia justifican el salto de calidad de 8 a 12 pasos. La medición dice que sí hay diferencia visible; el umbral es de producto.

**Nota de método:** son corridas únicas con carga variable de GPU, así que el orden es sólido pero diferencias de 2–3 s no deben leerse como precisas.

## 16. La nitidez no es la calidad: el operador vio grano, no anatomía

El operador señaló el render **sin LoRA a 8 pasos y CFG 3,0** (47,6 s, 5.994 MiB) diciendo que "en esta se nota la calidad". Se comprobó sobre el mismo recorte, y **los dos juicios son compatibles pero distintos**.

### 16.1 La métrica le da razón… a medias

Varianza laplaciana sobre el **mismo recorte** de las cuatro (comparación válida aquí, porque el contenido es idéntico):

| Configuración | Nitidez (lap var) | Tiempo | Pico |
|---|---:|---:|---:|
| sin LoRA · 8 pasos · CFG 3,0 — *la del operador* | 849,1 | 47,6 s | 5.994 MiB |
| turbo · 8 pasos · CFG 1,0 | 620,3 | 40,4 s | 6.686 MiB |
| turbo · 12 pasos · CFG 1,0 | 710,3 | 49,7 s | 6.686 MiB |
| **sin LoRA · 12 pasos · CFG 3,0** | **952,4** | 52,2 s | **6.394 MiB** |

La imagen señalada **es más nítida que el turbo** por métrica. Pero la métrica mide **contraste local de alta frecuencia**, y el CFG 3,0 produce **grano** en el fieltro y en la piel: eso infla el número sin que haya más detalle anatómico.

### 16.2 A 3,5× el orden se invierte

Recorte de manos, mismo encuadre en las tres:

- **sin LoRA 8 pasos (la señalada):** anatomía legible, pero **piel de cera**, puntas de los dedos blandas, **sin uñas**, sin pliegues en los nudillos.
- **turbo 8 pasos:** **pliegues en los nudillos y uñas visibles**, mejor superficie. **Las mejores manos de las tres.**
- **sin LoRA 12 pasos:** pliegues y uñas presentes, ligeramente menos nítidas que el turbo.

**Conclusión:** lo que el operador vio es real —la imagen tiene **textura fotográfica y grano**, y a tamaño completo se lee mejor que las demás—, pero ese grano **no es detalle**. En anatomía de manos, el turbo a 8 pasos gana.

### 16.3 Las dos configuraciones defendibles

| Criterio | Configuración | Coste |
|---|---|---|
| Textura fotográfica y **menor pico** | **sin LoRA · 12 pasos · CFG 3,0** | 52,2 s · **6.394 MiB** |
| **Mejores manos**, lo más rápido | turbo · 8 pasos · CFG 1,0 | **40,4 s** · 6.686 MiB |

La intuición del operador apuntaba a CFG 3,0 sin LoRA, y **llevada a 12 pasos es la mejor de las cuatro en textura y en pico** (952,4 y 6.394 MiB), además de tener las segundas mejores manos. El turbo conserva la ventaja en manos y en tiempo.

### 16.4 Tercera corrección de método del día

La varianza laplaciana **premia el grano**. Usarla sola como proxy de calidad es un error del mismo tipo que juzgar por la imagen completa o descartar los 12 pasos sin mirarlos. En este documento se usa solo para **describir textura**, nunca para concluir anatomía, y la anatomía se decide mirando el recorte ampliado.

## 17. El turbo compra velocidad quitando el negative prompt — y eso se ve

El operador insistió en que su imagen tiene mejores detalles, coloración, estilo, botellas y que **las pieles no se ven gomosas**. Tenía razón, y la causa es mecánica, no impresionista.

### 17.1 La prueba en el log

| Configuración | Pases de condicionamiento | Negative prompt |
|---|---:|---|
| CFG 3,0 (sin LoRA) | **2** | codificado: `(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch)` |
| CFG 1,0 (turbo) | **1** | **nunca se codifica** |

Con CFG 1,0 **no hay rama negativa**: el negative prompt es inerte. Eso explica las dos cosas a la vez:

- **Por qué el turbo es rápido:** la mitad de los pases de condicionamiento y, por paso, una sola evaluación en vez de dos. La velocidad **no viene del LoRA**, viene de eliminar el guidance.
- **Por qué la piel cambia:** el negative prompt es justamente lo que empuja **fuera** de "illustration, 3d, 2d, painting". Sin él, la tendencia por defecto del modelo a la superficie plástica queda sin contrapeso.

### 17.2 Lo que sí y lo que no es medible en el color

La saturación global y la métrica de colorfulness salen **casi idénticas**:

| Configuración | Saturación | Colorfulness |
|---|---:|---:|
| sin LoRA 8p CFG 3,0 | 61,4 % | 54,2 |
| turbo 8p CFG 1,0 | 61,3 % | 55,3 |
| sin LoRA 12p CFG 3,0 | **63,4 %** | **58,1** |

Así que lo que el operador describe como "mejor coloración" **no es saturación**. Es **variedad de objetos y materiales**: en el recorte del fondo, el render con CFG 3,0 tiene botellas de siluetas y cristales distintos (ámbar, verde, transparente) mientras el de CFG 1,0 tiende a botellas alargadas y uniformes con etiquetas pálidas. Y es **mate frente a brillo**: la piel del CFG 3,0 es mate; la del turbo tiene un brillo aceitoso en frente y pómulo.

### 17.3 Corrección del veredicto

Mi §16 puso las manos por delante y llamó al turbo "mejores manos". Sigue siendo cierto **en el recorte de manos**, pero **ponderarlo como criterio principal fue un error de proporción**: las manos son una región del encuadre; la piel, las botellas, el estilo y el color son el encuadre entero.

**Configuración de calidad: CFG 3,0 sin LoRA.** A 12 pasos es además la más nítida (952,4) y la de **menor pico de todas** (6.394 MiB) a 52,2 s.

**El turbo queda como opción de velocidad, con su coste declarado:** 40,4 s a cambio de perder el negative prompt.

### 17.4 Lo que esto implica para el despliegue

Si el proyecto sirve imágenes donde importan piel y materiales —y así parece—, **CFG 3,0 es la configuración correcta y el turbo es una concesión**, no una mejora. La elección real es *calidad de material frente a 12 segundos*.

## 18. Diseño de animación: qué existe, qué se verificó y qué está bloqueado

### 18.1 El LoRA de animación, verificado

`axiomofmind/Moss-image-animated-lora` → `MOSS-Image-Animated-LoRA-ComfyUI.safetensors`, **74.379.584 B**, SHA-256 `A99173F545271DCD43BBB79483C60FECEAB447B80841D2391936A60672E41934`.

**L1: `(504 / 504) LoRA tensors have been applied`.** A 12 pasos y CFG 3,0: **67,9 s**, pico **6.922 MiB**.

El resultado es lo que su card promete: **fotograma de película de animación 3D** — materiales pulidos, especulares limpios, caras idealizadas, seis jugadores más el barman. Es tratamiento *cartoon dimensional*, no cel 2D.

**Aviso de coherencia con el criterio del operador:** este LoRA **suaviza la piel a propósito**. Es lo contrario de lo que pedía (piel mate y fotográfica), y aquí el suavizado es la estética buscada, no un defecto. Conviven mal: elegir animación es elegir esa superficie.

### 18.2 El VAE RGBA: incompatible con este build

`paralaif/MOSS-Manga-Alpha-Image-LoRA` → `vae/flux2_klein_alpha_rgba_vae.safetensors`, **336.222.776 B**. Se probó como `--vae`:

```
[E] VAE tensor 'first_stage_model.decoder.conv_out.bias' has wrong shape: got [4,1,1,1], expected [3,1,1,1]
[E] VAE tensor 'first_stage_model.decoder.conv_out.weight': got [3,3,128,4], expected [3,3,128,3]
[E] VAE tensor 'first_stage_model.encoder.conv_in.weight': got [3,3,4,128], expected [3,3,3,128]
[E] model metadata validation failed
```

Es un VAE de **4 canales (RGBA)**; el cargador de `sd.cpp` **exige 3** y falla en la validación de metadatos. Exit 1 en 1,0 s, sin imagen.

Se buscó una salida: el runtime maneja imágenes RGBA como **entrada** y en el upscaler, pero **no hay ningún flag de salida alfa** (`--help` solo menciona alpha en el scheduler). **La transparencia está cerrada en este build**, y con ella el uso de `moss_manga_alpha_image_lora` y `moss_alpha_v1` tal como fueron diseñados.

**Consecuencia para animación:** se pueden generar fotogramas, pero **no assets con fondo transparente**. Para composición haría falta recortar después o cambiar de runtime.

### 18.3 Inventario de estilos disponible

**Estilo puro** (todos safetensors salvo donde se indique):

| LoRA | Tamaño | Nota |
|---|---:|---|
| Anime / seinen (`axiomofmind`) | 74.365.536 | **GGUF, verificado 504/504** |
| Animated Character 3D (`axiomofmind`) | 74.379.584 | **verificado 504/504**, este informe |
| Gouache / Psychedelic / Beauty (`axiomofmind`) | 74,4 MB cada uno | GGUF, descargados |
| Impressionism (`Kandoo`) | 74.470.552 | puro estilo pictórico |
| **Blue Archive style** (`RunningHubAI`) | 129.017.232 | ilustración anime de juego |
| Fizgig Look (`ShootTheSound`) | 2.221.764.612 | "look" completo, 2,2 GB |
| kale-img-1 (`suhaaspk`) | 148.697.160 | estilo propio |
| myjc / myjs / mylow (`deadman44`) | ~300 MB cada uno | estilos personales |
| Gabriel DropOut (`quarterturn`) | 297.333.192 | personaje/estilo |

**Técnicos, que no son estilo pero sirven al diseño:**

| LoRA | Tamaño | Para qué |
|---|---:|---|
| **Hires LoRA** (`comfyanonymous`, 7 versiones) | 132–182 MB | alta resolución, del autor de ComfyUI |
| **NextScene** (`AdwolfCzar`) | 145.157.240 | continuidad de escena — relevante para animación |
| 12-step turbo / 4-step adapter | 284 MB / 1,19 GB | velocidad |

**Control de línea y estructura** (`thedeoxen`, 290 MB cada uno): **lineart**, **scribble**, canny, normal, depth, segmentation, pose. Los dos primeros son la base de un flujo de diseño de animación: dibujo de línea → imagen.

**Personajes con IP:** Frieren, Alya, Emilia, Marin (`tachiyumi`, 145 MB cada uno), 83 celebridades (`pmczip`) y `shuiwu22` (`ACCC1380`). **Copyright: no utilizables en entrega comercial sin derechos.**

### 18.4 Lo que queda por verificar

De los de control (`lineart`, `scribble`) **no se ha probado ninguno**. Son los que más aportarían a un flujo de diseño de animación y cuestan 290 MB cada uno.

## 19. Auditoría de licencias del catálogo de estilos

Criterio aplicado: **un LoRA no tiene licencia propia independiente.** Hereda la del modelo base —MOSS-Image es Apache 2.0, así que la base no bloquea— y añade lo que declare su autor. Y **la ausencia de licencia no es permiso**: sin licencia, el derecho de autor aplica por defecto y no hay cesión de uso comercial. Se revisó también si había fichero `LICENSE` en el repo cuando el card no declaraba nada.

**No es asesoría legal:** es una lectura conservadora de ingeniería, y ante un uso comercial serio conviene revisión jurídica.

### 19.1 Conservan el uso comercial (Apache 2.0)

| Adaptador | Licencia | Tamaño |
|---|---|---:|
| **Impressionism** (`Kandoo`) | apache-2.0 | 74.470.552 |
| **NextScene v1** (`AdwolfCzar`) | apache-2.0 | 145.157.240 |
| **myjc / myjs / mylow** (`deadman44`) | apache-2.0 | 915.941.960 (3 ficheros) |
| **thedeoxen × 7** (lineart, scribble, canny, normal, depth, segmentation, pose) | apache-2.0 | 2.031.780.352 |

**Total: 3.167.350.104 B = 3,17 GB** (2,95 GiB).

### 19.2 Descartados

| Adaptador | Motivo |
|---|---|
| **Blue Archive style** (`RunningHubAI`) | **sin licencia declarada y sin fichero LICENSE** → sin permiso. Además referencia IP de un juego |
| **Gabriel DropOut** (`quarterturn`) | **`cc-by-nc-4.0`** — la cláusula NC prohíbe el uso comercial de forma explícita. Suma IP de personaje |
| **Hires LoRA** (`comfyanonymous`) | **sin licencia declarada y sin fichero LICENSE** → sin permiso |
| **Frieren / Alya / Emilia / Marin** (`tachiyumi`) | sin licencia **y** personajes con copyright |
| **83 celebridades** (`pmczip`) | licencia `other` (ambigua) **y** derechos de imagen de personas reales |
| **shuiwu22** (`ACCC1380`) | sin licencia **y** personaje con copyright |

### 19.3 Dos avisos que no quiero enterrar

**El Hires LoRA es la baja más dolorosa.** Es el que el operador señaló como solución "donde fallan los otros modelos", y se cae **solo por papeleo**: `comfyanonymous` no declaró licencia ni incluyó fichero. La solución no es técnica, es **pedirle permiso al autor** — un mensaje, no una negociación. Si concede Apache o MIT, entra sin más.

**`deadman44` pasa por licencia pero el sujeto es dudoso.** Los nombres `myjc`, `myjs`, `mylow` sugieren estilos personales o de personaje. Apache 2.0 sobre los pesos **no concede derechos de imagen ni de personaje**: si están entrenados sobre una persona real o una IP, la licencia del fichero no cubre el uso comercial del resultado. **Verificar antes de entregar.**

### 19.4 Lo que este filtro deja en pie

Con el filtro aplicado, el catálogo comercialmente limpio queda en **cuatro estilos/estructurales**: Impressionism, NextScene (continuidad de escena, el que importa para vídeo), tres estilos personales de dudoso sujeto, y **el set completo de control de `thedeoxen`** — que es, con diferencia, la parte más valiosa y la única que habilita un flujo de producción (lineart y scribble sin probar todavía).

**Ninguno de los descartados era una capacidad irremplazable; el único con valor técnico único era el Hires LoRA, y su bloqueo es administrativo.**

## 20. Los sin licencia, probados — y el coste real cuando el destino es vídeo

Se descargaron y probaron los descartados por licencia, a petición del operador y **solo para evaluación interna**. Todo a 12 pasos, CFG 3,0, offload, seed 7.

| LoRA | L1 | Tiempo | Pico | Veredicto |
|---|---|---:|---:|---|
| **Hires v0.7** a **1280×1280** | 600/600 | **222,9 s** | **7.482 MiB** | funciona: 1280² limpio, sin duplicaciones, caras y manos definidas |
| **Blue Archive** a 1024² | 328/328 | 72,0 s | 7.218 MiB | entrega el estilo: ilustración anime limpia, ojos detallados, paleta pastel |
| **Frieren** a 1024² (cara) | 492/492 | 64,7 s | 6.566 MiB | **el personaje se reconoce**: orejas de elfo, gemelos, ojos verdes, túnica |

**Los tres mapean sin perder un tensor.** El de Hires es el único que además resuelve el problema de alta resolución: a 1280² no aparecen cabezas duplicadas ni anatomías rotas, que es el modo típico de fallar al subir resolución.

### 20.1 El número que decide: segundos por fotograma

Si el destino son vídeos de YouTube, la cuenta por imagen se vuelve brutal:

| Configuración | s/fotograma | 5 s de vídeo (40 fotogramas) | 10 s (80) |
|---|---:|---:|---:|
| turbo · 8 pasos · CFG 1,0 | **40,4** | **26,9 min** | 53,9 min |
| base · 12 pasos · CFG 3,0 | 52,2 | 34,8 min | 69,6 min |
| Frieren · 12 pasos | 64,7 | 43,1 min | 86,3 min |
| Blue Archive · 12 pasos | 72,0 | 48,0 min | 96,0 min |
| **Hires · 1280²** | **222,9** | **148,6 min** | 297,2 min |

**Cinco segundos de vídeo con el Hires son dos horas y media.** Con el turbo, media hora. El Hires no es una opción para vídeo aunque su calidad sea la mejor; es una opción para piezas fijas.

### 20.2 Sobre personajes: el problema no es el fichero

Los LoRAs de personaje **funcionan técnicamente**, y Frieren se reconoce sin ambigüedad. Pero **ninguna licencia de fichero concede derechos sobre el personaje**: Frieren, Marin, Emilia, Alya y Gabriel DropOut son IP de anime comercial. En un canal monetizado eso es **riesgo de infracción**, con independencia de lo que declare el repo.

**Para "faceless con rostros" conviene separar dos cosas:**
- **Rostros genéricos**: sin problema. El modelo base ya los produce bien.
- **Personajes reconocibles de terceros**: viables para probar, no para publicar.

### 20.3 Lo que esto deja para la poda

Con el criterio declarado —**dos supervivientes, uno para calidad y otro para rapidez**— los datos apuntan a:

| Ranura | Candidato | Por qué |
|---|---|---|
| **Calidad** | **base · 12 pasos · CFG 3,0 · sin LoRA** | mejor piel y materiales; el negative prompt activo es lo que evita el aspecto plástico |
| **Rapidez** | **turbo · 8 pasos · CFG 1,0** | 40,4 s por fotograma, un 23 % menos que la base |

Y la advertencia: **ninguno de los LoRAs de estilo probados mejora la piel**. Anime y Animated la suavizan a propósito; Blue Archive la estiliza. Si "calidad" significa piel fotográfica, el ganador no es un LoRA sino **el modelo desnudo con su negative prompt**.

## 21. El ritmo real del formato disuelve la tensión volumen/calidad

El operador corrigió el supuesto: **no son vídeos fotograma a fotograma.** Son vídeos faceless de 15 minutos con **60–70 imágenes**. Eso son **4,0–4,7 imágenes por minuto de vídeo**, una cada 13–15 segundos: ritmo documental, no animación.

### 21.1 Coste por vídeo

| Modelo | 60 imágenes | 65 | 70 |
|---|---:|---:|---:|
| klein 8 pasos | 22 min | **24 min** | 26 min |
| **MOSS 12 pasos CFG 3,0** | 52 min | **57 min** | 61 min |
| MOSS + Hires 1280² | 3,7 h | 4,0 h | 4,3 h |

### 21.2 Rendimiento por jornada de 8 horas

| Modelo | Vídeos de 15 min por día de máquina |
|---|---:|
| klein | **19,8** |
| MOSS en calidad | **8,5** |
| MOSS + Hires | 2,0 |

**Ocho vídeos y medio al día con el modelo de calidad.** Ningún canal publica a ese ritmo: **el volumen deja de ser una restricción** y la premisa "klein para volumen" queda refutada por los números del propio operador.

### 21.3 Asignación corregida de los dos modelos

| Rol | Modelo | Configuración | Por qué |
|---|---|---|---|
| **Producción** | **MOSS** | 12 pasos, CFG 3,0 | el vídeo final; 57 min por vídeo es asumible |
| **Borrador** | **klein** | 8 pasos | explorar prompts y encuadres barato: 10 variaciones cuestan 4 h frente a 9,5 h con MOSS |
| Retirado | Z-Image | — | no gana en producción ni en borrador |

**Hires entra como opción de pieza especial**, no de rutina: 4 horas por vídeo.

### 21.4 Consecuencia para la poda de modelos

**MOSS es el modelo principal**, no el secundario. **Z-Image sale** porque queda dominado en las dos ranuras. **Se mantienen dos modelos** con roles distintos: producción y borrador.

Esto invierte la recomendación anterior, y conviene dejar constancia de por qué: la anterior se apoyaba en un supuesto de fps que el operador nunca dio. **La lección es la misma que en las correcciones anteriores — decidir sobre un supuesto propio en vez de sobre el dato del usuario.**
