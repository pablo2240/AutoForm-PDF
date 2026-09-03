"""
Dictionary of field synonyms and negative exclusion rules for AI PDF filling.
Helps the LLM accurately match form labels and ignore non-applicable sections.
"""

from typing import Dict, List

FIELD_SYNONYMS: Dict[str, List[str]] = {
    "razon_social": [
        "Nombre empresa", "Nombre / Razon social", "Nombre / Razón Social", 
        "Nombre Entidad", "Razon social", "Razón Social", "Denominación Social",
        "Empresa", "Organización"
    ],
    "nit": [
        "nit", "NIT", "Numero Nit", "Número NIT", "Nro nit", "Nro. NIT", 
        "cc/ce/pas/nit", "rut", "RUT", "Identificación Tributaria", "Número de Identificación Tributaria"
    ],
    "numero_cedula": [
        "cedula", "cédula", "c.c", "C.C.", "c.c", "identificacion", "identificación", 
        "identidad", "id", "ID", "Nro", "No. Documento", "Número de Documento", 
        "Número de Cédula", "Cédula de Ciudadanía", "NÚMERO ID", "NUMERO ID", 
        "Número ID", "Numero ID", "Nro ID", "No. ID", "No ID", "NÚMERO DE ID", 
        "NUMERO DE ID", "Número de ID", "Numero de ID", "Num ID"
    ],
    "tipo_documento": [
        "Tipo de Documento", "Tipo ID", "Tipo de ID", "Clase de Documento", 
        "C.C. / CE / Pasaporte", "Tipo Doc", "Tipo Documento"
    ],
    "lugar_expedicion_rep": [
        "Lugar de Expedición", "Lugar de Expedicion", "Expedida en", "Ciudad de Expedición", 
        "Ciudad de Expedicion", "De (ej: C.C. No. ____ de ____)", "Expedición", "Expedicion",
        "de", "De", "de:", "De:"
    ],
    "nacionalidad": [
        "Nacionalidad", "Nacionalidad 1", "Nacionalidad 2", "País de Origen", 
        "Nacionalidad del Representante", "Nacionalidad / Origen", "Nacionalidad del Solicitante"
    ],
    "representante_legal": [
        "Nombre del Representante Legal", "Representante Legal", "Nombre Representante Legal",
        "Nombres y Apellidos del Representante", "Apoderado General / Gerente", "Gerente General",
        "Representante Legal Principal", "Apellidos y Nombres", "Nombres y Apellidos",
        "Apellidos y Nombres / Razón Social", "Nombres y Apellidos / Razón Social",
        "Nombre y Apellidos", "Apellidos y Nombre"
    ],
    "representante_nombre": [
        "Nombres", "Primer Nombre / Segundo Nombre", "Nombres del Representante",
        "Primer Nombre", "Segundo Nombre"
    ],
    "representante_apellido": [
        "Apellidos", "Primer Apellido / Segundo Apellido", "Apellidos del Representante",
        "Primer Apellido", "Segundo Apellido"
    ],
    "contacto_nombre": [
        "Contacto Principal", "Persona de Contacto", "Nombre de Contacto", 
        "Contacto Comercial", "Nombre del Contacto", "Contacto"
    ],
    "contacto_cargo": [
        "Cargo del Contacto", "Cargo Contacto", "Cargo"
    ],
    "direccion_principal": [
        "direccion", "dirección", "residencia", "sede", "ubicacion principal", "ubicación principal",
        "Dirección Domicilio", "Dirección Principal", "Domicilio Principal", "Dirección de Notificación"
    ],
    "ciudad": [
        "Ciudad", "Municipio", "Localidad", "Ciudad Principal", "Ciudad / Municipio"
    ],
    "departamento": [
        "Departamento", "Provincia / Departamento", "Dpto."
    ],
    "pais": [
        "País", "Pais", "País de Domicilio", "País de Origen"
    ],
    "telefono": [
        "Teléfono", "Telefono", "Tel.", "Tel", "Teléfono Fijo / Contacto", 
        "Teléfono Fijo", "Número Telefónico", "Teléfono Principal", "PBX"
    ],
    "celular_rep": [
        "Celular", "Teléfono Móvil", "Telefono Movil", "Número de Celular", "Móvil"
    ],
    "correo_rep": [
        "Correo Electrónico", "Correo Electronico", "Email", "E-mail", "Email / E-mail", 
        "Correo de Notificación / Contacto", "Correo de Notificación", "Correo Electrónico Principal",
        "Correo", "Email Corporativo"
    ],
    "pagina_web": [
        "Página Web", "Pagina Web", "Página Web / Sitio Web", "Sitio Web", 
        "URL / Portal Web", "Dirección Web", "Direccion Web", "Web", "Portal Web"
    ],
    "dv": [
        "dv", "DV", "D.V.", "Dígito de Verificación", "Digito de Verificacion", 
        "Dígito Verificador", "Digito Verificador", "Dígito", "Digito"
    ],
    "entidad_bancaria": [
        "Banco", "Entidad Bancaria", "Entidad Bancaria / Financiera", "Nombre del Banco", 
        "Institución Financiera", "Entidad Financiera", "Banco Principal"
    ],
    "numero_cuenta": [
        "Número de Cuenta", "Numero de Cuenta", "No. Cuenta / Cta. No.", "No. Cuenta", 
        "Cuenta Bancaria No.", "Cuenta No.", "No. de Cuenta", "No. Cuenta Bancaria"
    ],
    "tipo_cuenta": [
        "Tipo de Cuenta", "Tipo Cuenta", "Modalidad de Cuenta", "Tipo de Producto", "Clase de Cuenta"
    ],
    "sucursal": [
        "Sucursal / Agencia", "Sucursal", "Sucursal del Banco", "Agencia"
    ]
}

IGNORE_RULES: List[str] = [
    "1. NO LLENAR SECCIONES PARA EXTRANJEROS: La empresa y el representante legal son colombianos (nacionales). Ignora tablas o casillas tituladas 'Persona Extranjera', 'No Residentes', 'Extranjero', 'Foreign Entity', 'Ciudadanos extranjeros'.",
    "2. NO LLENAR SECCIONES DE USO EXCLUSIVO DE LA ENTIDAD: Ignora cualquier sección con títulos como 'Espacio reservado para la entidad', 'Uso exclusivo de la empresa/banco', 'Aprobación interna', 'Para uso de la oficina', 'Firma y sello del funcionario'.",
    "3. NO LLENAR SECCIONES PEP: Ignora y NO respondas nada en secciones '6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)', 'PEP', preguntas sobre si es PEP; déjalas totalmente vacías.",
    "4. NO LLENAR SECCIONES 'SÓLO PARA CLIENTES' NI 'SÓLO PARA VENDEDORES': Si la sección dice 'SÓLO PARA CLIENTES', 'DATOS DE CONTACTO SÓLO PARA CLIENTES', 'SÓLO PARA VENDEDORES' o similar, ignórala COMPLETAMENTE. No llenes ningún campo de esa sección aunque tengas los datos.",
    "5. NO MEZCLAR NI DESPLAZAR VALORES ENTRE CAMPOS: Cada valor va EXACTAMENTE al campo que lo solicita. Nunca pongas 'Colombiana' en un campo de Teléfono ni 'Guillermo Humberto' en un campo de Nacionalidad. Si la etiqueta NO coincide exactamente con el tipo de dato, NO pongas nada.",
    "6. REPRESENTANTE LEGAL PRINCIPAL: La persona facultada es Guillermo Humberto Cañón Sarria (C.C. 98555384 de Envigado). Completa sus datos en los campos de Representante Legal.",
    "7. APELLIDOS Y NOMBRES COMPLETOS: Cuando un campo pida 'Apellidos y Nombres' o 'Nombres y Apellidos' en una sola casilla, escribe el nombre completo: 'Guillermo Humberto Cañón Sarria'.",
    "8. NÚMERO ID Y LUGAR DE EXPEDICIÓN ('DE'): Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID' o 'CÉDULA', llénalo con '98555384'. Si al lado hay una casilla 'de' (ej. C.C. No. _____ de _____), pon: 'Envigado'.",
    "9. NACIONALIDAD: Cuando un campo pida EXACTAMENTE 'Nacionalidad' o 'Nacionalidad 1', escribe 'Colombia'. No pongas 'Colombiana', ni fecha, ni expedición. Si hay 'Nacionalidad 2' o campo de segunda nacionalidad, déjala completamente vacía.",
    "10. CONTACTO PRINCIPAL (SOLO SI LA SECCIÓN NO ES EXCLUSIVA PARA CLIENTES): Cuando una sección solicite 'Contacto Principal', llena: Nombre: Guillermo Humberto Cañón Sarria, Celular: 3104120217, Correo: guillermo.canon@iaclatam.com, Cargo: Representante Legal.",
    "11. TABLAS CON MÚLTIPLES FILAS: Llena ÚNICAMENTE la primera fila (Fila 1). Las filas 2, 3, 4, 5 deben quedar vacías.",
    "12. CAMPOS 'OTRA' / 'OTRO': Dejar completamente vacíos.",
    "13. OPCIONES MÚLTIPLES: Ignorar bloques de opciones múltiples genéricas.",
    "14. NO DUPLICACIÓN EN CAMPOS CONTIGUOS: No repitas el mismo dato en campos contiguos con finalidades distintas.",
    "15. DOBLE NACIONALIDAD / NACIONALIDAD 2: Solo se reporta la nacionalidad principal ('Colombia'). Cualquier campo de segunda nacionalidad debe quedar vacío."
]

def get_dictionary_context() -> str:
    """Formats synonyms and exclusion rules as structured text for LLM prompts."""
    lines = ["\n--- DICCIONARIO DE SINÓNIMOS DE CAMPOS ---"]
    for canonical, synonyms in FIELD_SYNONYMS.items():
        syn_str = ", ".join(f'"{s}"' for s in synonyms)
        lines.append(f"• Campo '{canonical}': coincide con [{syn_str}]")
    
    lines.append("\n--- REGLAS ESTRICTAS DE EXCLUSIÓN (QUÉ NO LLENAR) ---")
    for rule in IGNORE_RULES:
        lines.append(f"• {rule}")
    
    return "\n".join(lines)
