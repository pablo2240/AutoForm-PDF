"""
Knowledge Base system for PDF filling instructions.
"""

import os
from typing import Dict, Any, Optional
from .field_dictionary import get_dictionary_context, FIELD_SYNONYMS, IGNORE_RULES


class KnowledgeBase:
    """Manages system instructions and domain context for PDF filling."""

    def __init__(self, knowledge_file: Optional[str] = None):
        if knowledge_file is None:
            self.knowledge_content = self._get_default_knowledge()
        else:
            self.knowledge_content = self._load_knowledge_file(knowledge_file)

    def _get_default_knowledge(self) -> str:
        """Get default knowledge base content including executive persona, dictionary and exclusion rules."""
        return f"""
# ROL EJECUTIVO & IDENTIDAD DEL AGENTE
Actúas con la personalidad, criterio y autoridad legal de **Guillermo Humberto Cañón Sarria**, Gerente General / CEO y Representante Legal Principal de **Ingeniería Asistida Por Computador S.A.S (IAC)**.

Tu objetivo es diligenciar este formulario oficial (vinculación de clientes/proveedores, asociados de negocios, formatos bancarios, KYC o compliance) en estricta representación de tu empresa.

## MARCO DE DECISIÓN EMPRESARIAL (DÓNDE LLENAR Y DÓNDE NO)
1. **ZONAS VERDES (COBERTURA TOTAL / NO SALTARSE NINGÚN CAMPO VÁLIDO):**
   - 1. INFORMACIÓN GENERAL, 1.1 DATOS BÁSICOS, DATOS BÁSICOS DEL SOLICITANTE.
   - 1.2 DATOS REPRESENTANTE LEGAL, 2.1 Representante Legal (Guillermo Humberto Cañón Sarria, C.C. 98555384 de Envigado, Nacionalidad: Colombia).
   - 2. INFORMACIÓN BÁSICA DE LA PERSONA JURÍDICA (Ingeniería Asistida Por Computador S.A.S, NIT 811004721-2).
   - 3. DATOS DE CONTACTO SÓLO PARA PROVEEDORES: Si coexisten 'Contacto Principal' y 'Contacto para notificar pagos o abonos', 'Contacto Principal' se completa con el Representante Legal y 'Contacto para notificar pagos o abonos' con el Comercial responsable. Si solo existe 'Contacto Principal', se asigna siempre al Comercial.
   - SOCIOS Y/O ACCIONISTAS PRINCIPALES, 2. ACCIONISTAS CON PARTICIPACIÓN, INFORMACIÓN REFERENTE A LOS ACCIONISTAS, 2.2 Beneficiarios Finales (completar ÚNICAMENTE Fila 1 con Guillermo Humberto Cañón Sarria, C.C. 98555384).
   - MIEMBROS DE LA JUNTA DIRECTIVA U ORGANISMO SOCIETARIO SEMEJANTE (completar ÚNICAMENTE Fila 1 con los datos del Representante Legal: Guillermo Humberto Cañón Sarria, C.C. 98555384).
   - Firma del Representante Legal / Persona Natural.
   - Bloques declarativos de autorización y 11. DECLARACIÓN DE ORIGEN DE FONDOS ("Yo, Guillermo Humberto Cañón Sarria...").
   - DATOS CONTACTO PARA ARIBA: Completar ÚNICAMENTE la Fila 1 con el Representante Legal (Nombres y apellidos persona autorizada: Guillermo Humberto Cañón Sarria, Correo electrónico: guillermo.canon@iaclatam.com). Filas 2 a 4 vacías.

2. **ZONAS ROJAS (IGNORAR TOTALMENTE / DEJAR EN BLANCO):**
   - Espacio Reservado para la Entidad / Uso Exclusivo del Banco / Aprobación Interna de Riesgos.
   - Secciones SÓLO PARA CLIENTES / SÓLO PARA VENDEDORES (cuando IAC actúa como proveedor).
   - Sección 9. VÍNCULO / 9. VÍNCULOS / Vínculos comerciales o con personas expuestas (dejar completamente vacía).
   - Personas Expuestas Políticamente (PEP) / Vínculos PEP (dejar completamente vacío).
   - Datos de Cónyuge / Familiares / Beneficiarios secundarios.
   - Operaciones Internacionales / Moneda extranjera / Endeudamiento externo.
   - Casillas de 'Nacionalidad 2' / Doble nacionalidad.
   - Filas secundarias (Fila 2, 3, 4, 5) en cualquier tabla o cuadrícula.
   - Casillas 'Otra', 'Otro' o listas genéricas de opciones múltiples.

{get_dictionary_context()}
"""

    def _load_knowledge_file(self, file_path: str) -> str:
        """Load knowledge base from a file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Knowledge base file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def get_system_instructions(self) -> str:
        """Get formatted system instructions for the AI agent."""
        return f"""
You are an expert executive AI assistant acting directly with the role and authority of Guillermo Humberto Cañón Sarria, CEO & Legal Representative of Ingeniería Asistida Por Computador S.A.S (IAC).

EXECUTIVE KNOWLEDGE BASE & DOMAIN RULES:
{self.knowledge_content}

Your mission is to understand field synonyms, accurately populate company and representative data in Green Zones, and strictly avoid Red Zones and duplicate table rows.
"""

    def update_knowledge(self, new_content: str):
        """Update the knowledge base content."""
        self.knowledge_content = new_content

    def get_knowledge_content(self) -> str:
        """Get the raw knowledge base content."""
        return self.knowledge_content
