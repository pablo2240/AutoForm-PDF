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
        "Ciudad de Expedicion", "De (ej: C.C. No. ____ de ____)", "Expedición", "Expedicion"
    ],
    "representante_legal": [
        "Nombre del Representante Legal", "Representante Legal", "Nombre Representante Legal",
        "Nombres y Apellidos del Representante", "Apoderado General / Gerente", "Gerente General",
        "Representante Legal Principal"
    ],
    "representante_nombre": [
        "Nombres", "Primer Nombre / Segundo Nombre", "Nombres del Representante",
        "Primer Nombre", "Segundo Nombre"
    ],
    "representante_apellido": [
        "Apellidos", "Primer Apellido / Segundo Apellido", "Apellidos del Representante",
        "Primer Apellido", "Segundo Apellido"
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
        "País", "Pais", "País de Domicilio", "Nacionalidad / Origen", "País de Origen"
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
    "entidad_bancaria": [
        "Banco", "Entidad Bancaria", "Entidad Bancaria / Financiera", "Nombre del Banco", 
        "Institución Financiera", "Entidad Financiera"
    ],
    "numero_cuenta": [
        "Número de Cuenta", "Numero de Cuenta", "No. Cuenta / Cta. No.", "No. Cuenta", 
        "Cuenta Bancaria No.", "Cuenta No.", "No. de Cuenta"
    ],
    "tipo_cuenta": [
        "Tipo de Cuenta", "Tipo Cuenta", "Modalidad de Cuenta", "Tipo de Producto"
    ],
    "sucursal": [
        "Sucursal / Agencia", "Sucursal", "Sucursal del Banco", "Agencia"
    ]
}

IGNORE_RULES: List[str] = [
    "1. NO LLENAR SECCIONES PARA EXTRANJEROS: La empresa y el representante legal son colombianos (nacionales). Ignora tablas o casillas tituladas 'Persona Extranjera', 'No Residentes', 'Extranjero', 'Foreign Entity', 'Ciudadanos extranjeros'.",
    "2. NO LLENAR SECCIONES DE USO EXCLUSIVO DE LA ENTIDAD: Ignora cualquier sección con títulos como 'Espacio reservado para la entidad', 'Uso exclusivo de la empresa/banco', 'Aprobación interna', 'Para uso de la oficina', 'Firma y sello del funcionario'.",
    "3. NO LLENAR DATOS DE LA CONTRAPARTE/CLIENTE: Si el formulario es de vinculación o registro, llena únicamente la sección de 'DATOS DEL SOLICITANTE / EMPRESA / TITULAR / PROVEEDOR'. No llenes datos del comprador o cliente si la casilla pertenece a la empresa que emitió el formulario.",
    "4. NO LLENAR CONTACTOS COMERCIALES DE TERCEROS NO APLICABLES: Ignora campos como 'Datos de contacto sólo para proveedores' cuando sea una sección de terceros o referencias comerciales externas.",
    "5. REPRESENTANTE LEGAL PRINCIPAL: La persona facultada y principal para firmar y representar a la empresa es Guillermo Humberto Cañón Sarria (C.C. 98555384 de Envigado). Completa siempre sus datos en los campos de Representante Legal.",
    "6. CAMPOS 'OTRA' / 'OTRO': Si una casilla o etiqueta dice 'OTRA', 'OTRO', 'OTRAS', 'OTROS' (por ejemplo campos residuales 'Otra:', '¿Cuál?', 'Otras operaciones', etc.), NUNCA pongas datos y déjala completamente vacía.",
    "7. OPCIONES MÚLTIPLES: Cuando en los formularios se presenten grupos o bloques de opciones múltiples (listas para marcar múltiples alternativas, encuestas de opciones múltiples o bloques de selección no específicos), ignóralas y no escribas nada.",
    "8. NÚMERO ID: Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID', 'NRO ID' o similar, debe llenarse con el número de Cédula de Ciudadanía del Representante Legal (98555384)."
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
