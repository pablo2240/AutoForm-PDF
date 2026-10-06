# Biblioteca de formularios de referencia

Esta carpeta es la **fuente de verdad** de la biblioteca: el conocimiento extraído (etiquetas, secciones, posiciones, vectores) vive en una caché SQLite derivada (`backend/data/reference_library/library.db`) que se reconstruye en cualquier momento.

La **familia** de cada formulario se define, en este orden, por:
1. `manifest.json` de esta carpeta: `{"families": {"archivo.pdf": "familia"}}`
2. el nombre de la subcarpeta (`docs/referencias/<familia>/archivo.pdf`)
3. si no hay ninguna, `sin_clasificar` (nunca se usa como familia conocida al clasificar)

```bash
python scripts/reference_library.py sync              # añade, actualiza y elimina según la carpeta
python scripts/reference_library.py add form.pdf --family proveedor
python scripts/reference_library.py search "Identificación fiscal"
python scripts/reference_library.py classify nuevo.pdf
```

Para crecer de 5 a miles de formularios basta con soltar más PDFs, anotar su familia y ejecutar `sync` (o subirlos por `/api/reference-library/documents`). Ver `docs/adr/0013-reference-library-embeddings-and-dynamic-few-shot.md`.
