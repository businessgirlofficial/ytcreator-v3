# kaggle_kernel_meta/

Esta carpeta existe porque la API de Kaggle exige un archivo
`kernel-metadata.json` para poder hacer `kernels_push` (que es lo
que dispara la ejecucion remota de tu notebook).

**Antes de usar el Agente 3.2 contra tu Kaggle real, edita
`kernel-metadata.json`:**

- `id`: debe coincidir EXACTO con `KAGGLE_KERNEL_SLUG` en tu `.env`
- `code_file`: el nombre de tu notebook real
  (probablemente `YouTube_AI_Studio_v7_HIBRIDO.ipynb`)
- `dataset_sources`: debe coincidir con `KAGGLE_DATASET_SLUG`,
  para que tu notebook tenga el dataset de prompts montado en
  `/kaggle/input/<slug>/`
- `enable_gpu`: dejalo en `"true"` (necesitas la T4 x2)

Si tu notebook ya existe en Kaggle, puedes generar este archivo
automaticamente parado en la carpeta donde tengas una copia local
del notebook, corriendo:

    kaggle kernels init -p .

Eso crea un kernel-metadata.json a partir de un kernel que ya
exista con tu cuenta, y solo te falta verificar que los campos
coincidan con lo de arriba.
