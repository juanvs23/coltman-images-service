# Segmind-Vega — Stage 2 sobre GGUF Q8_0 de terceros

> **Purga del 2026-11-19.** El operador ordenó conservar solo `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`. Se borraron **todos** los pesos, renders y logs de candidatos rechazados, y también los de las configuraciones descartadas de MOSS. Lo único que queda en disco es el fichero DMD, sus tres componentes de runtime (VAE FLUX.2, Qwen3.5-9B Q4_K_M, `tokenizer.json`) y los tres renders/logs del DMD. **Las listas de artefactos de este documento son históricas**: describen lo que existió durante la medición, no lo que hay hoy.

> **CERRADO EL 2026-11-18: Vega está DESCARTADA por decisión del operador**, tomada a partir de la prueba seria de grupo de personas (`p10-b3-segmind-vega-quality-group-test.md`). Los pesos ya no están en disco — ni el fp16 ni el GGUF — y el gate de LoRA L1/L2/L3 se cierra **por decisión, no por un pass**. Este documento y el de calidad se conservan como **registro de un rechazo medido**. Los 11 renders, los 15 logs y los registros se mantienen para que cada cifra siga siendo verificable.

**Estado:** Stage 2 ejecutado y **candidato eliminado**.  
**Fecha:** 2026-11-18
**Artefacto:** `vonjack/hyper-sd-v1_5-segmind-vegart-gguf` → `segmind-vega-q8_0.gguf`
**Documentos relacionados:** `p10-b3-segmind-vega-documentation.md` (Stage 0/1), `p10-b3-viable-candidates-elimination-ledger.md` (ledger vivo), `p10-b3-stage2-test-sheet.md` (hoja de Stage 2).

---

## 0. Corrección de un error previo

En la ronda anterior se afirmó que **no existía ninguna conversión GGUF de Segmind-Vega**, ni oficial ni de terceros, y que el fp16 era "la única vía". **Esa afirmación era incorrecta.** Existía una conversión de terceros, publicada el 2024-05-07, que la búsqueda web del momento no había surfaced. El error se corrige aquí con la evidencia del artefacto, no con una promesa de buscar mejor la próxima vez.

La regla operativa que sale de este error: *"no encontré una versión GGUF"* no es lo mismo que *"no existe una versión GGUF"*. La primera frase es un resultado de búsqueda; la segunda es un hecho del mundo y exige una consulta estructurada al API del modelo —árbol de ficheros y búsqueda por etiquetas— antes de afirmarse.

## 1. Identidad del artefacto

| Campo | Valor | Origen |
|---|---|---|
| Repositorio | `vonjack/hyper-sd-v1_5-segmind-vegart-gguf` | API de Hugging Face |
| Fichero | `segmind-vega-q8_0.gguf` | árbol del repositorio |
| Tamaño | `2,132,007,776 bytes` | `stat` local |
| LFS SHA-256 | `189bbfe7b33e2a55c8f0f631e36e1e0b96d5ee3e96d595f9f2e1a354c51841a1` | API, **verificado localmente** |
| Licencia declarada | `apache-2.0` | frontmatter del repo de terceros |
| Descargas / likes | 246 / 4 | API |
| Última actualización | 2024-05-07 | API |
| README | 31 bytes: solo `license: apache-2.0` | repo de terceros |

**Huella de contenido (cabecera GGUF leída por HTTP Range, sin descargar el fichero entero):**

- GGUF versión 3, **1.525 tensores**, **0 entradas de metadatos** (`general.*` ausente).
- Tipos: **1.379 × Q8_0** + **146 × F16** (capas sensibles conservadas en f16).
- Reparto de tensores, que es la forma exacta que espera `stable-diffusion.cpp`:

| Prefijo | Tensores | Componente |
|---|---:|---|
| `model.diffusion_model.*` | 564 | UNet / DiT |
| `cond_stage_model.transformer.*` | 196 | CLIP-L |
| `cond_stage_model.1.*` | 517 | CLIP-G (incluye `model.text_projection.weight`) |
| `first_stage_model.*` | 248 | VAE (encoder + decoder) |

Es decir: **el GGUF es el modelo completo en un solo fichero**, no solo el UNet. No necesita sidecars de texto ni VAE.

### 1.1 Debilidades de la conversión (declaradas, no resueltas)

- **Sin procedencia escrita.** El README tiene 31 bytes y el GGUF no lleva metadatos. No hay script de conversión, ni comando, ni versión de `sd.cpp` usada, ni verificación contra el fp16. La reproducibilidad **no está demostrada**, solo es plausible.
- **Comunidad baja.** 246 descargas y 4 likes no cumplen el criterio de "comunidad media-alta, estable" aplicado a los repos de referencia. El modelo base sí tiene comunidad; **la conversión no**.
- **Licencia coherente por herencia.** El repositorio declara `apache-2.0`, que es lo que corresponde a Vega. No hay cláusula restrictiva, pero tampoco hay texto de licencia *del conversor* que auditar.
- **Verdad no verificada:** que este GGUF sea el mismo modelo que el fp16 oficial. El nombre, la arquitectura de tensores y la estructura coinciden; los pesos no se han comparado tensor a tensor.

## 2. Runtime usado

El runtime ya presente en el proyecto, sin ninguna modificación:

- `vendor/stable-diffusion.cpp`, commit `532d2c15c430a785a712b2d94281f04e733008a4` (2026-11-15).
- Binario `vendor/stable-diffusion.cpp/build/bin/sd-cli` (`stable-diffusion.cpp version master-1106-532d2c1`).
- Medición con el **método canónico del proyecto** (`tests/e2e/flux2-klein/resource_profile.py`): `nvidia-smi --query-gpu=memory.used` muestreado cada 250 ms desde antes del arranque del hijo hasta después de su salida.

El runtime **detecta el modelo sin hints externos**:

```
[I] Version: SDXL (Vega)  --- diffusion_engine.cpp:982
```

y reparte los componentes:

```
[I]   VAE          params    159 MiB, compute reserve  1024 MiB -> compute CUDA0, params CUDA0
[I] auto-fit: --backend "diffusion=CUDA0,te=CUDA0,vae=CUDA0"
[I] total params memory size = 2041.33MB (VRAM 2041.33MB, RAM 0.00MB):
      text_encoders 835.45MB(VRAM), diffusion_model 1046.19MB(VRAM), vae 159.68MB(VRAM)
```

## 3. Mediciones

Prompt fijo `a lighthouse at dusk, calm sea, dramatic sky, no text`, seed `7`, `4` pasos, CFG `2.0`, negativo vacío. Base de la tarjeta: **8.188 MiB** totales; línea base en el host con la GPU ya ocupada por otro consumidor: **291–295 MiB**.

| Perfil | Resolución pedida | Res. realmente renderizada | exit | Tiempo | Pico GPU | Δ vs base | Imagen |
|---|---|---|---:|---:|---:|---:|---|
| resident | 1280×720 | **1280×768** | 0 | 5,92 s | **6.482 MiB** | 6.187 | sí |
| resident + `--force-sdxl-vae-conv-scale` | 1280×720 | 1280×768 | 0 | 5,58 s | 6.482 MiB | 6.187 | sí |
| `--offload-to-cpu` | 1280×720 | **1280×768** | 0 | 6,10 s | **4.602 MiB** | 4.307 | sí |
| resident | 1024×1024 | 1024×1024 | 0 | 6,16 s | **6.754 MiB** | 6.459 | sí |
| `--offload-to-cpu` | 1024×1024 | 1024×1024 | 0 | 6,29 s | **4.874 MiB** | 4.579 | sí |

**Las cinco ejecuciones producen imagen y salen con código 0.** Artefactos y logs en `run/p10-stage2/segmind-vega/gguf/`.

### 3.1 La resolución 720 no es 720

El runtime **redondea la petición al alza a un múltiplo de 64**:

```
[W] align generation request up 1280x720 to 1280x768 (multiple=64) --- request.cpp:224
[I] generate_image 1280x768 --- image.cpp:954
```

El PNG resultante mide 1280×768 (verificado con PIL sobre los cinco ficheros). Cualquier comparación de "720p" contra este perfil debe hacerse contra **1280×768**, no contra 720.

### 3.2 De dónde viene el pico

Reparto leído del log del propio runtime:

| Concepto | VRAM |
|---|---:|
| Pesos: text encoders + diffusion model + VAE | 2.041 MiB |
| Buffer de cómputo del UNet | 461 MiB |
| **Buffer de cómputo del decoder del VAE** | **3.600 MiB** |
| **Total observado (pico)** | **6.482 MiB** |

**El pico no lo caused los pesos: lo causa el decoder del VAE.** Los pesos cuantizados ocupan 2,04 GiB; el decode a 1280×768 pide 3,6 GiB de buffer. Esto es el mismo riesgo que ya estaba anotado para SDXL canónico en `p10-b3-sdxl-canonical-report.md`, y es el número que decide si hay sitio para LoRAs.

### 3.3 El flag de conv-scale no hace nada aquí

`sd-cli` avisa:

```
[W] No valid VAE specified with --vae or --force-sdxl-vae-conv-scale flag set, using Conv2D scale 0.031
```

Forzarlo con `--force-sdxl-vae-conv-scale` produce un PNG **byte-idéntico**: `mean_abs_diff = 0.0000`, `max_abs_diff = 0`, `0 / 983.040` píxeles distintos. El aviso es benigno en este camino. **No es un defecto de la conversión.**

## 4. Calidad de imagen

> **CORREGIDO el 2026-11-18.** Lo que sigue describe lo que se midió con **4 pasos y CFG 2.0**, que **no es el régimen de este modelo**. El model card exige CFG ≈ 9.0 con negative prompt; con esa configuración el modelo produce escenas fotorrealistas legibles y el contraste se duplica. Las conclusiones de calidad de esta sección **no son válidas** y se conservan solo como registro de la corrida. Ver `p10-b3-segmind-vega-quality-group-test.md`, que contiene la prueba seria, el control que demuestra la diferencia y el juicio corregido.

Inspección visual de los PNG produced:

- **1280×768:** faro claramente visible sobre mar en calma, cielo dramático, sin texto. Semántica correcta y completa respecto al prompt.
- **1024×1024:** mar, cielo de atardecer y sol en el horizonte. **El faro no aparece.** El mismo prompt y la misma seed producen una composición distinta al cambiar la relación de aspecto; el modelo no reprodujo la composición.
- **Contraste bajo en ambos** (desvío típico de luminancia 33,3 sobre un rango 0–255; media ~105 y ~99). La imagen es correcta pero plana, no contrastada.

Esto no está verificado contra referencia: **no hay render fp16 de control**, porque el camino fp16 murió por OOM antes de producir imagen. El juicio de calidad es, por tanto, **absoluto** ("se ve bien, se ve plano") y no **comparativo** ("peor o mejor que el fp16 oficial").

## 5. Lo que NO se ha hecho

- **L1 / L2 / L3 de LoRA: no ejecutados.** Es el gate que decide si Vega entra.
- **Limpieza / reversibilidad:** no medida más allá de que el proceso hijo termina y libera la VRAM (el siguiente probe arranca con la base otra vez).
- **Comparación de pesos** GGUF vs fp16 oficial.
- **Reproducibilidad** de la conversión.

## 6. Lo que este cambio hace con el ledger

La eliminación por VRAM de Vega (§11 del ledger) estaba apoyada en una medición del camino **diffusers fp16**: pico 6.724 MiB y OOM pidiendo 18 MiB más. Esa medición sigue siendo válida **para el camino fp16**.

Lo que cambia es que **Vega tiene ahora una segunda vía que sí renderiza**. Y la observación importante es que **cuantizar apenas contribuyó a lo que rescató**: el pico GGUF resident (6.482 MiB) es apenas **242 MiB menor** que el pico fp16 por diffusers (6.724 MiB). Lo que hace posible el render no es el GGUF en sí, es **la disposición de memoria de `sd.cpp`** —pesos 2,04 GiB en lugar de ~6,7 GiB de tensores diffusers materializados en fp16, con el decoder del VAE como pico dominante y controlable.

## 7. Estado y siguiente paso

**Vega sale del "kill por VRAM" y vuelve al campo como candidato #1, por la vía GGUF**, con una reserva explícita sobre el margen de LoRA:

- A **1024×1024 resident** el pico es 6.754 MiB → quedan **~1.434 MiB libres** sobre 8.188 MiB. El presupuesto de LoRA declarado en `host.yaml` es **3.200 MiB**. **Resident no llega al presupuesto de LoRA.**
- A **1024×1024 con `--offload-to-cpu`** el pico es 4.874 MiB → quedan **~3.314 MiB libres**. **Con offload sí llega al presupuesto de 3.200 MiB**, con un coste de ~0,1 s por render respecto a resident (6,29 s vs 6,16 s).

**Siguiente paso obligatorio: L1/L2/L3 en el perfil `--offload-to-cpu` a 1024×1024**, que es el único perfil que cumple hoy el piso de VRAM + presupuesto de LoRA. Si L2 (efecto no nulo) falla, Vega sale igual.

## 8. Hallazgo colateral: `segmind-vegart-q8_0.gguf`

El mismo repositorio contiene `segmind-vegart-q8_0.gguf`, **del mismo tamaño exacto** (`2,132,007,776 bytes`) y con **la misma estructura de 1.525 tensores** que `segmind-vega-q8_0.gguf`. Por nombre y por geometría parece ser **Vega con el LoRA LCM de VegaRT fusionado** — es decir, una variante de 1–4 pasos.

**No se ha descargado, no se ha medido y no se ha renderizado.** Queda anotado como el siguiente artefacto a probar, con la advertencia de que es el mismo modelo base y por tanto hereda el mismo riesgo de memoria en el decoder del VAE.
