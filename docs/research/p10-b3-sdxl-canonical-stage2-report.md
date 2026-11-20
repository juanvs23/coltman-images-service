# SDXL canonical Q8_0 (C3A) — Stage 2 medido

> **Purga del 2026-11-19.** El operador ordenó conservar solo `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`. Se borraron **todos** los pesos, renders y logs de candidatos rechazados, y también los de las configuraciones descartadas de MOSS. Lo único que queda en disco es el fichero DMD, sus tres componentes de runtime (VAE FLUX.2, Qwen3.5-9B Q4_K_M, `tokenizer.json`) y los tres renders/logs del DMD. **Las listas de artefactos de este documento son históricas**: describen lo que existió durante la medición, no lo que hay hoy.

**Estado:** medido y viable en VRAM. **LoRA L1/L2/L3 pendientes.**
**Fecha:** 2026-11-19
**Artefacto:** `kostakoff/stable-diffusion-xl-base-1.0-GGUF` → `sd_xl_base_1.0_0_Q8_0.gguf`
**Runtime:** `sd.cpp` `532d2c1`, binario `sd-cli`
**Relacionados:** `p10-b3-viable-candidates-elimination-ledger.md` (§17), `p10-b3-segmind-vega-quality-group-test.md` (el candidato eliminado contra el que se compara)

---

## 1. Identidad del artefacto

| Campo | Valor |
|---|---|
| Repositorio | `kostakoff/stable-diffusion-xl-base-1.0-GGUF` |
| Fichero | `sd_xl_base_1.0_0_Q8_0.gguf` |
| Tamaño | `4.180.186.816 bytes` |
| SHA-256 | `c25a143954d00f6eed6235cbe0f26d2a4e68c9f3452bef33bc6ffa3b3073856b` — **verificado localmente** |
| Licencia del repo | `openrail++` |
| Descargas / actualización | 3.968 / 2026-03-06 |

**Huella de la cabecera GGUF** (leída por HTTP Range, sin descargar el fichero entero):

- GGUF v3, **2.513 tensores**, **0 metadatos** (`general.*` ausente).
- Tipos: **1.370 Q8_0 + 1.143 F16** — más de la mitad en f16, y por eso pesa 4,18 GB frente a los 2,13 GB del Q8_0 de Vega.
- Reparto: `model.diffusion_model` **1.680** (UNet), `conditioner.embedders` **585** (los dos CLIP), `first_stage_model` **248** (VAE).
- **Modelo completo en un fichero**: no necesita sidecars de texto ni VAE.

**Nomenclatura:** este GGUF usa la forma *diffusers* (`conditioner.embedders.0.*` / `.1.*`), no la de ComfyUI que usaba el de Vega. `sd.cpp` la convierte internamente (`conditioner.embedders.0.` → `cond_stage_model.`, `conditioner.embedders.1.` → `cond_stage_model.1.`, en `src/name_conversion.cpp`), y el modelo carga sin conversión previa.

## 2. Detección y reparto

```
[I] Version: SDXL  --- diffusion_engine.cpp:982
[I] total params memory size = 3996.05MB (VRAM 0.00MB, RAM 3996.05MB):
      text_encoders 925.92MB(RAM), diffusion_model 2910.44MB(RAM), vae 159.68MB(RAM)
```

Con `--offload-to-cpu` **los 3.996 MB de pesos viven en RAM** y se transmiten a VRAM cuando toca. El UNet de SDXL canónico pesa **2.910 MB** frente a los **1.046 MB** del de Vega: casi el triple, que es lo que explica la diferencia de tiempo.

## 3. Mediciones

Prompt canónico de grupo de personas del proyecto, negative prompt del model card, **CFG 7,0, 30 pasos**, 1024×1024, seeds 7 / 1234 / 42. La tarjeta tiene **8.188 MiB**; la línea base del host varió entre 605 y 717 MiB por otros consumidores.

| Perfil | seed | exit | Tiempo | Pico | Δ vs base | Libre en el pico | Render |
|---|---:|---:|---:|---:|---:|---:|---|
| `--offload-to-cpu` | 7 | 0 | 38,6 s | 5.188 MiB | 4.583 | **3.000 MiB** | 1024×1024 |
| resident | 7 | 0 | 37,1 s | **7.170 MiB** | 6.565 | 1.018 MiB | 1024×1024 |
| `--offload-to-cpu` | 1234 | 0 | 37,1 s | 5.300 MiB | 4.597 | 2.888 MiB | 1024×1024 |
| `--offload-to-cpu` | 42 | 0 | 37,1 s | 5.300 MiB | 4.583 | 2.888 MiB | 1024×1024 |

**Las cuatro corridas salen con código 0 y producen imagen a 1024×1024 exactos** — sin redondeo, porque 1024 ya es múltiplo de 64.

**`--offload-to-cpu` baja el pico casi 2 GB y no cuesta casi nada de tiempo:** 38,6 s frente a 37,1 s, un 4%. Y produce una imagen **byte-idéntica** a la resident (`0 de 1.048.576` píxeles distintos).

### 3.1 De dónde viene el pico

| Concepto | VRAM |
|---|---:|
| Buffer de cómputo del UNet | 492 MiB |
| **Buffer de cómputo del decoder del VAE** | **3.840 MiB** |
| Pesos (con offload) | 0 MiB en VRAM — 3.996 MB en RAM |

**El techo es el decoder del VAE, otra vez.** 3.840 MiB a 1024² frente a los 3.600 MiB de Vega a 1280×768: escala con los píxeles, no con el tamaño del modelo. Es el mismo muro que ya se documentó para Vega y para SDXL en el informe de Stage 0/1.

## 4. Calidad

Tres seeds, misma escena y misma configuración. Inspección visual:

**Lo que hace bien**

- **Manos: anatomía correcta, superficie gomosa.** Es la diferencia real contra Vega: cinco dedos, articulaciones, sin fusiones. Pero ampliado a 3× la piel es de maniquí — sin poros, sin arrugas, sin rojeces en nudillos, con brillos de silicona. La estructura está bien; la superficie no. Ver §4.1.
- **Fotorrealismo**: piel, tela, madera, cristal y luz de tungsteno, con la profundidad de campo que pide el prompt **de verdad** presente (fondo desenfocado, sujetos nítidos).
- **Caras sólidas y diferenciadas**: cinco rostros distintos en la seed 7, cuatro en la 1234, tres en la 42. Sin ojos derretidos ni asimetrías.
- **Coherencia física**: la seed 7 llega a poner un **barman reflejado en el espejo** detrás de la barra. Ningún objeto flotando.
- **Atmósfera**: verde de pared, madera, lámparas colgantes, botellas al fondo. La escena se sostiene.

**Lo que falla**

- **Conteo de personas**: el prompt pide seis jugadores más un barman. Salen cinco, cuatro y tres. Mejor que Vega (que daba tres a cinco), pero sigue corto.
- **Colapso de vestuario**: casi todos visten camisa blanca con chaleco y pajarita, tomado del rol de barman. La seed 1234 rompe el patrón con un jugador de camisa verde.
- **Texto**: la seed 1234 pinta un rótulo dorado ilegible en el centro de la mesa. Esperado en SDXL y admitido por el model card.
- **Cartas**: legibles como objetos, no como valores. Igual que en Vega.

**No verificado:** comparación contra la referencia oficial de SDXL. El juicio es absoluto, no contra un render de control.

## 4.1 La piel: se investigó y no es la cuantización

La primera lectura de las manos decía "correctas". Ampliadas a 3× **no lo son**: la anatomía es correcta, la **piel es gomosa** — superficie uniforme, sin poros, sin arrugas, sin rojeces en los nudillos, con brillos propios de silicona. El operador lo señaló y tenía razón.

Se probaron cuatro sospechosos, en orden de coste:

**1. Pasos.** 50 pasos en lugar de 30. **No mejora la piel** y añade artefactos: las fichas se funden en masas verdosas y las cartas se emborronan. 58,0 s.

**2. CFG.** CFG 5 en lugar de 7. **No mejora la piel** y añade artefactos: el cuero del borde de la mesa se llena de textura falsa. 36,9 s.

**3. Cuantización — el A/B que con Vega era imposible.** El mismo repositorio publica `sd_xl_base_1.0_0_bf16.gguf` (6.937.943.840 B, SHA-256 `34dd73230348039590610f94227e19a0279057fbb5e2db959255054ad0a6ad43`, verificado). Cabecera comprobada: **cero tensores cuantizados** — UNet 1.046 BF16 + 634 F16, decoder del VAE 69 BF16 + 69 F16. Misma seed, mismo prompt, misma configuración (30 pasos, CFG 7, 1024², offload): 51,5 s, pico 6.314 MiB, exit 0.

**Resultado: el bf16 no mejora la piel, y en las manos sale peor.** Las manos del centro se funden en una sola masa, la mano en primer plano es un bulto liso, y las cartas quedan como manchas ruidosas. **La cuantización queda exonerada.**

**4. El modelo.** Comparado contra el ancla actual del proyecto, **FLUX.2 [klein] 4B Q4_K_M**, sobre el mismo prompt: la mano del render de klein muestra **nudillos marcados, pliegues, uña, tendones y textura mate**. Las manos de SDXL son cilindros lisos con brillo.

> Nota metodológica: la varianza laplaciana no sirve como métrica entre estas tres imágenes, porque cada recorte cubre contenido distinto (el de klein es sobre todo fondo oscuro). La comparación es visual, y a 3× es inequívoca.

**Conclusión:** la piel gomosa es una propiedad del **renderizado de piel de SDXL base** en este pipeline, no de la cuantización, no de los pasos y no del CFG. El único camino conocido para cerrarla es un LoRA de detalle o de piel — que es exactamente lo que el gate de LoRA mediría.

## 5. Comparación con Vega (eliminada)

Mismo prompt, mismas seeds, misma familia de configuración:

| | Vega Q8_0 (eliminada) | SDXL Q8_0 (C3A) |
|---|---|---|
| Configuración | CFG 9, 25 pasos | CFG 7, 30 pasos |
| Tiempo a 1024² | 16,5 s | **37,1 s** |
| Pico resident | 6.766 MiB | **7.170 MiB** |
| Pico offload | 4.886 MiB | 5.188–5.300 MiB |
| Manos | **fallan en las 4 imágenes** | **correctas en las 3 seeds** |
| Conteo pedido 7 | 3–5 | 3–5 |
| Objeto flotante | sí (una seed) | no |

**SDXL canónico cuesta 2,2× el tiempo y ~400 MiB más de pico, y a cambio arregla las manos.** Ese es el intercambio, y para el uso del proyecto las manos pesan más que 20 segundos.

## 6. Margen para LoRA

| Perfil | Libre en el pico | Presupuesto declarado (`host.yaml`) | ¿Cabe? |
|---|---:|---:|---|
| resident | 1.018 MiB | 3.200 MiB | **No** |
| `--offload-to-cpu` | 2.888–3.000 MiB | 3.200 MiB | **No, por 200–312 MiB** |

**Pero el número no cierra la pregunta, y conviene decirlo claro:** con offload los 3.996 MB de pesos están en RAM, así que un LoRA que se fusione con el UNet puede costar **RAM y no VRAM**. La cuenta de "libre contra presupuesto" es una cota gruesa; lo que decide es L1/L2/L3 medido.

## 7. Lo que NO se ha hecho

- **LoRA L1/L2/L3: no ejecutados.** No hay ningún LoRA de SDXL en disco: el proyecto solo tiene los tres de FLUX.2 [klein] (`model/assets/loras/flux2-klein-4b-gguf-q4/`), que **no aplican** a esta arquitectura. Hace falta descargar un LoRA SDXL.
- **Q4_K (C3B): no medido.** Queda como la variante de 2,80 GB si el margen de Q8_0 no alcanza.
- **Comparación de pesos** contra el checkpoint oficial de Stability.
- **Reproducibilidad de la conversión** de `kostakoff` (el repo no documenta la receta en el árbol consultado).

## 8. Veredicto

**SDXL canónico Q8_0 pasa el piso de VRAM a 1024×1024 y arregla la anatomía de las manos que mató a Vega — pero su piel es peor que la del modelo que el proyecto ya sirve.**

Ese matiz cambia la decisión. Contra Vega gana en lo que importa (cinco dedos con articulación, sin objetos flotando). Contra **FLUX.2 [klein] 4B**, que ya está instalado y corre a 4.305 MiB de pico, pierde en superficie: la piel de klein muestra nudillos, pliegues, uñas y textura; la de SDXL es goma lisa.

Y cuesta **2,2× el tiempo** (37,1 s contra 16,5 s de Vega), **~400 MiB más de pico** que Vega y muy por encima de los 4.305 MiB de klein.

**Por tanto SDXL canónico no es un reemplazo del ancla.** Su valor real es el **ecosistema de LoRA**, que es donde el gate L1/L2/L3 tiene sentido: si un LoRA de detalle o de piel cierra la brecha de superficie, entonces SDXL sí aporta algo que klein no tiene. Si no, no aporta nada que el proyecto no tenga ya.

**Siguiente paso obligatorio:** LoRA L1/L2/L3 con `--offload-to-cpu`, incluyendo un LoRA de detalle/piel en la comparación. L2 (efecto no nulo) sigue siendo el kill gate. Sin LoRA SDXL en disco, ese gate necesita una descarga.

## 9. Artefactos

Bajo `run/p10-stage2/sdxl-canonical/`, excluido por el ignore file:

- `render-sdxl-q8_0-offload-1024-s7.png`, `...-s1234.png`, `...-s42.png`, `render-sdxl-q8_0-resident-1024-s7.png`
- `sd-cli-sdxl-q8_0-*.log` — los cuatro logs, con el censo de pesos y los buffers
- `stage2-report.md` — registro JSON de las cuatro corridas
- `sd_xl_base_1.0_0_Q8_0.gguf` — el checkpoint (4,18 GB)
- `../probe.py` — el probe reutilizable para el resto del campo
