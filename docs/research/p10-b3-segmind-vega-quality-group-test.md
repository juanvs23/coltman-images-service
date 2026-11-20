# Segmind-Vega — Pruebas serias de calidad: grupo de personas

> **Purga del 2026-11-19.** El operador ordenó conservar solo `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`. Se borraron **todos** los pesos, renders y logs de candidatos rechazados, y también los de las configuraciones descartadas de MOSS. Lo único que queda en disco es el fichero DMD, sus tres componentes de runtime (VAE FLUX.2, Qwen3.5-9B Q4_K_M, `tokenizer.json`) y los tres renders/logs del DMD. **Las listas de artefactos de este documento son históricas**: describen lo que existió durante la medición, no lo que hay hoy.

> **CERRADO EL 2026-11-18: esta prueba es la base de la eliminación de Vega.** El operador descartó el candidato tras leerla. Los pesos ya no están en disco y el gate de LoRA L1/L2/L3 se cierra por decisión, no por un pass. Los renders se conservan como evidencia.

**Estado:** calidad medida con la configuración que el modelo declara. **Corrige un juicio anterior inválido.**  
**Fecha:** 2026-11-18
**Modelo:** Segmind-Vega Q8_0 GGUF (`segmind-vega-q8_0.gguf`, SHA-256 `189bbfe7…41a1`)
**Runtime:** `sd.cpp` `532d2c1`, binario `sd-cli`
**Relacionados:** `p10-b3-segmind-vega-gguf-stage2-report.md`, `p10-b3-viable-candidates-elimination-ledger.md` §15

---

## 0. Corrección: el juicio de calidad anterior no valía

En `p10-b3-segmind-vega-gguf-stage2-report.md` §4 se registró que Vega produce imágenes "correctas pero planas", con desvío típico de luminancia **33,3** y contraste bajo, y que a 1024² el faro no aparecía.

**Ese juicio se hizo con 4 pasos y CFG 2.0, que no es el régimen de este modelo.** El model card de Vega lo dice explícitamente:

> "Please do use negative prompting and a **CFG around 9.0** for the best quality!"

Y recomienda el negative prompt:

> `(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch)`

Vega es un modelo **destilado de SDXL por destilación de conocimiento**, no un modelo destilado para pocos pasos. Los 4 pasos con CFG 2 son el régimen de un LCM (VegaRT), no del checkpoint base. Por tanto el "contraste bajo" y la "composición que no aparece" eran artefactos de una muestra sin converger, **no propiedades del modelo**.

El control de este documento lo demuestra de forma directa: mismo prompt, misma seed, mismo modelo, CFG 2 / 4 pasos produce una **mancha irreconocible**; CFG 9 / 25 pasos produce una escena fotorrealista legible.

## 1. Diseño de la prueba

| Parámetro | Valor | Por qué |
|---|---|---|
| Prompt | `Photorealistic scene inside a dimly lit bar: six people around a round poker table, one of them dealing playing cards, chips and half-empty glasses on the green felt, a bartender in a white shirt and apron wiping a glass behind a wooden counter, warm tungsten lamps, cigarette smoke in the air, shallow depth of field, 50mm lens` | Es el prompt canónico del propio proyecto (`tests/e2e/flux2-klein/resource_profile.py`): escena de grupo, oclusiones, manos, caras y un rol diferenciado (barman). Permite comparación directa con FLUX.2 [klein]. |
| Negative prompt | `(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch)` | El que recomienda el model card. |
| CFG | 9.0 | El que recomienda el model card. |
| Pasos | 25 | Régimen de convergencia para un no-LCM; el card no fija número y el default de diffusers es 50. |
| Resoluciones | 1024×1024 (nativa) y 1280×768 (clase 720p de esta tarjeta) | |
| Seeds | 7, 1234, 42 | Tres seeds distintas para medir consistencia, no una. |
| Perfiles | resident y `--offload-to-cpu` | El perfil de producción es el que cabe con LoRAs. |

## 2. Mediciones

| Corrida | Resolución | Perfil | exit | Tiempo | Pico GPU | Imagen |
|---|---|---|---:|---:|---:|---|
| seed 7 | 1024×1024 | resident | 0 | 16,43 s | 6.766 MiB | sí |
| seed 1234 | 1024×1024 | resident | 0 | 16,49 s | 6.766 MiB | sí |
| seed 42 | 1024×1024 | resident | 0 | 16,60 s | 6.766 MiB | sí |
| seed 7 | 1280×768 | resident | 0 | 16,01 s | 6.494 MiB | sí |
| seed 7 | 1024×1024 | `--offload-to-cpu` | 0 | 16,64 s | **4.886 MiB** | sí |
| seed 7 | 1024×1024 | resident, **CFG 2 / 4 pasos (control)** | 0 | 6,16 s | 6.766 MiB | sí |

**El pico no depende del número de pasos ni del CFG.** Con 4 pasos y con 25 pasos el pico resident es el mismo (6.754 vs 6.766 MiB), porque sigue dominado por el buffer del decoder del VAE (3.600 MiB). Lo que cambia con los pasos es el **tiempo**: 6,2 s → 16,5 s.

**`--offload-to-cpu` no cuesta calidad ni tiempo apreciable:** la imagen es **byte-idéntica** a la resident (`mean_abs_diff = 0.000000`, `max = 0`, **0 de 1.048.576** píxeles distintos) y tarda 16,64 s frente a 16,43 s. Cuesta **1.880 MiB menos de pico** y no cuesta nada más.

## 3. Contraste medido

Desvío típico de luminancia sobre los PNG:

| Configuración | σ luminancia |
|---|---:|
| CFG 9 / 25 pasos (seeds 7, 1234, 42) | **66,0 / 67,7 / 64,9** |
| CFG 2 / 4 pasos (control) | **29,1** |

La configuración correcta **más que duplica** el rango tonal. El "contraste bajo" registrado antes era un síntoma de muestreo sin converger.

## 4. Lo que las imágenes muestran

### 4.1 Lo que hace bien

- **Fotorrealismo convincente** para un UNet de 1.046 MiB de diffusion model en VRAM. Piel, tela, madera, cristal y luz de tungsteno se leen como fotografía, no como ilustración.
- **Caras sólidas** en las tres seeds: sin ojos derretidos, sin dentaduras rotas, sin asimetrías grotescas.
- **Iluminación coherente**: las lámparas del techo producen reflejos plausibles en el cristal y en la mesa, y la profundidad de campo que pide el prompt aparece de verdad (fondo desenfocado, sujetos nítidos).
- **El barman lleva delantal** en dos de las cuatro escenas, incluida la de 1280×768. El detalle de rol se respeta cuando la composición lo permite.
- **Consistencia entre seeds**: las tres producen escenas del mismo tipo, con el mismo lenguaje visual y el mismo nivel de acabado. No hay una seed "buena" y dos rotas.

### 4.2 Lo que hace mal

- **Manos: el defecto consistente y el más grave.** En las cuatro imágenes hay al menos una mano con dedos fundidos, sin articulación o directamente convertida en un bulto. Es el fallo clásico y aquí aparece **siempre**, no de vez en cuando.
- **Conteo de personas: falla.** El prompt pide **seis jugadores más un barman** (siete). Se obtienen **tres, cuatro o cinco**, nunca siete. En la seed 1234 son tres y no hay barman identificable.
- **Colapso de vestuario:** en casi todas las escenas **todos** los presentes llevan camisa blanca, porque el prompt describe al barman así. El atributo de un rol se propaga a la escena.
- **Objetos que no se sostienen:** en la seed 1234 hay un **vaso flotando en el aire** sin mano que lo sujete. Es un fallo de coherencia física, no de estética.
- **Cartas ilegibles:** las caras de las cartas están garabateadas y la baraja se acumula en un montón caótico. Coincide exactamente con lo que el propio model card advierte sobre el texto.
- **Fidelidad de composición compleja: parcial.** El model card lo admite con todas las letras: *"may encounter difficulties in … maintaining the fidelity of complex compositions"*.

### 4.3 Lo que la prueba confirma del model card

El card advierte dos limitaciones y **ambas se reproducen**:

> "faces challenges in achieving absolute photorealism, **especially in human depictions**"

Cierto en el detalle fino: la escena es fotorealista y las caras están bien, pero **las manos rompen la ilusión**, que es exactamente el modo en que falla la representación humana.

> "may encounter difficulties in incorporating clear text and maintaining the fidelity of complex compositions"

Cierto: cartas ilegibles y conteo de personas incorrecto.

## 5. Veredicto

| Criterio | Resultado |
|---|---|
| Fotorrealismo de escena | **Pasa** |
| Caras | **Pasa** |
| Manos | **Falla de forma consistente** |
| Conteo exacto de sujetos | **Falla** |
| Coherencia física de objetos | **Falla intermitente** (vaso flotante) |
| Texto / símbolos | **Falla** (esperado y declarado) |
| Consistencia entre seeds | **Pasa** |
| Coste en VRAM | 6.766 MiB resident / **4.886 MiB offload** a 1024² |
| Coste en tiempo | 16,5 s a 1024², 25 pasos |

**Lectura honesta:** Vega produce escenas de grupo **fotográficamente creíbles y con encuadre y luz convincentes**, y falla donde este tipo de modelo siempre falla —manos, conteo, objetos en el aire, texto—. No es un modelo de "grupo de personas con manos correctas". Es un modelo de **atmósfera y material** a coste bajo.

**Para el caso de uso del proyecto** (imágenes de acompañamiento, no retrato de precisión) eso puede ser suficiente; para cualquier entrega donde las manos o el número exacto de personas importen, **no lo es**.

## 6. Implicación sobre el gate de Stage 2

Este documento **no cierra** el gate: los LoRA L1/L2/L3 siguen sin ejecutarse. Pero cambia la pregunta. Antes la duda era "¿cabe en VRAM?". Ahora la duda es "¿cabe, y sus defectos de manos y conteo son aceptables para el uso previsto?". Lo primero está respondido: **cabe**, incluso con el presupuesto de LoRA de 3.200 MiB, usando `--offload-to-cpu`.

**Nota operativa: cualquier evaluación futura de calidad debe usar CFG ~9.0, negative prompt del card y ≥25 pasos.** Medir este modelo con 4 pasos y CFG 2 es medir el runtime, no el modelo.

## 7. Artefactos

Todos bajo `run/p10-stage2/segmind-vega/gguf/`, que el ignore file excluye:

- `warm-render-1024x1024-group-1024-s7-cfg9-25.png`
- `warm-render-1024x1024-group-1024-s1234-cfg9-25.png`
- `warm-render-1024x1024-group-1024-s42-cfg9-25.png`
- `warm-render-1280x768-group-1280x768-s7-cfg9-25.png`
- `warm-render-1024x1024-group-1024-s7-cfg9-25-offload.png`
- `warm-render-1024x1024-group-1024-s7-cfg2-4-CONTROL.png`
- `sd-cli-group-*.log` — logs del runtime de cada corrida
- `stage2-gguf-report.md` — registro JSON acumulado
