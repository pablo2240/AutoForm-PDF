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
    "tipo_empresa": [
        "Tipo de Empresa", "Naturaleza Jurídica", "Naturaleza de la Empresa", 
        "Tipo de Persona Jurídica", "Tipo de Entidad", "Clase de Empresa"
    ],
    "tipo_sociedad": [
        "Tipo de Sociedad", "Forma Jurídica", "Tipo Societario", "Estructura Jurídica"
    ],
    "codigo_ciiu": [
        "CIIU", "Código CIIU", "Codigo CIIU", "CIIU (Cod)", "Actividad Económica (CIIU)", 
        "Actividad CIIU", "CIIU Principal", "Código de Actividad"
    ],
    "actividad_economica": [
        "Actividad Económica", "Actividad Economica", "Objeto Social", "Actividad Principal", 
        "Descripción de la Actividad", "Sector / Actividad"
    ],
    "origen_fondos": [
        "Origen de Fondos", "Procedencia de Fondos", "Origen de los Recursos", 
        "Procedencia de Recursos", "Fuente de Recursos", "Origen de Bienes / Fondos"
    ],
    "pais_origen_fondos": [
        "País de Origen de Fondos", "Pais Origen Recursos", "País Origen de los Fondos"
    ],
    "gran_contribuyente": [
        "Gran Contribuyente", "¿Es Gran Contribuyente?", "Calidad de Gran Contribuyente"
    ],
    "autorretenedor": [
        "Autorretenedor", "¿Es Autorretenedor?", "Autorretenedor de Renta", "Resolución Autorretenedor"
    ],
    "responsable_iva": [
        "Responsable de IVA", "¿Es Responsable de IVA?", "Régimen de IVA", "Régimen Común"
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
    "3. NO LLENAR SECCIONES PEP (PERSONA EXPUESTA POLÍTICAMENTE): Ignora y NO respondas ni marques casillas en secciones como '6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)', 'PEP', 'PEPs', preguntas sobre si es PEP o tiene vínculos con PEP; déjalas totalmente vacías.",
    "4. NO LLENAR DATOS DE LA CONTRAPARTE/CLIENTE: Si el formulario es de vinculación o registro, llena únicamente la sección de 'DATOS DEL SOLICITANTE / EMPRESA / TITULAR / PROVEEDOR'. No llenes datos del comprador o cliente si la casilla pertenece a la empresa que emitió el formulario.",
    "5. NO LLENAR CONTACTOS COMERCIALES DE TERCEROS NO APLICABLES: Ignora campos como 'Datos de contacto sólo para proveedores' cuando sea una sección de terceros o referencias comerciales externas.",
    "6. REPRESENTANTE LEGAL PRINCIPAL: La persona facultada y principal para firmar y representar a la empresa es Guillermo Humberto Cañón Sarria (C.C. 98555384 de Envigado). Completa siempre sus datos en los campos de Representante Legal.",
    "7. APELLIDOS Y NOMBRES COMPLETOS: Cuando un campo pida 'Apellidos y Nombres' o 'Nombres y Apellidos' en una sola casilla o renglón, escribe el nombre completo: 'Guillermo Humberto Cañón Sarria'.",
    "8. NÚMERO ID Y LUGAR DE EXPEDICIÓN ('DE'): Cuando un campo indique 'NÚMERO ID', 'NUMERO ID', 'NO. ID' o 'CÉDULA', llénalo con '98555384'. Si inmediatamente a continuación o al lado hay una casilla que dice 'de' o 'De' (ej. No. ID: _____ de _____), pon el lugar de expedición: 'Envigado'.",
    "9. NACIONALIDAD: Cuando un campo pida 'Nacionalidad', hace referencia al país y debe escribirse 'Colombiana'.",
    "10. CONTACTO PRINCIPAL: Cuando una sección solicite datos de 'Contacto Principal' o 'Persona de Contacto', llena los campos con los datos del contacto/representante (Nombre: Guillermo Humberto Cañón Sarria, Teléfono/Celular: 3104120217, Correo: guillermo.canon@iaclatam.com, Cargo: Representante Legal).",
    "11. TABLAS CON MÚLTIPLES FILAS (SOLO PRIMERA FILA): En tablas o secciones con varias filas repetitivas (como socios/accionistas, miembros de junta directiva, cuentas bancarias adicionales, referencias comerciales o representantes suplentes), llena ÚNICAMENTE la primera fila (Fila 1). NO dupliques ni repitas los datos en la fila 2, 3, 4 ni siguientes.",
    "12. CAMPOS 'OTRA' / 'OTRO': Si una casilla o etiqueta dice 'OTRA', 'OTRO', 'OTRAS', 'OTROS', NUNCA pongas datos y déjala completamente vacía.",
    "13. OPCIONES MÚLTIPLES: Cuando se presenten bloques de opciones múltiples genéricas o encuestas de selección no específicas, ignóralas y no escribas nada.",
    "14. NO DUPLICACIÓN EN CAMPOS CONTIGUOS: No repitas el mismo dato en campos contiguos con finalidades distintas (por ejemplo: 'Sucursal' debe dejarse vacía si ya se colocó la 'Ciudad'; 'Segundo Apellido' no debe colocarse en 'Nombres')."
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
