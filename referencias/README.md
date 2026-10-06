# Biblioteca de formularios de referencia

Coloca aquí PDFs de ejemplo. La carpeta es la **fuente de verdad**: el conocimiento extraído (etiquetas, secciones, posiciones, vectores) vive en una caché SQLite derivada y se puede reconstruir en cualquier momento.

```
referencias/
├── manifest.json            (opcional) {"families": {"archivo.pdf": "familia"}}
└── pdf/
    └── <familia>/           el nombre de la subcarpeta es la familia del formulario
        └── formulario.pdf
```

```bash
python scripts/reference_library.py sync              # añade, actualiza y elimina según la carpeta
python scripts/reference_library.py add form.pdf --family proveedor
python scripts/reference_library.py search "Identificación fiscal"
python scripts/reference_library.py classify nuevo.pdf
```

Para crecer de 5 a miles de formularios basta con soltar más PDFs y ejecutar `sync` (o subirlos por `/api/reference-library/documents`). Ver `docs/adr/0013-reference-library-embeddings-and-dynamic-few-shot.md`.
