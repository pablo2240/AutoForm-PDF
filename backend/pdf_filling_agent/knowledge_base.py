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
1. **ZONAS VERDES (DILIGENCIAR CON PRECISIÓN):**
   - Identificación de la Persona Jurídica (Ingeniería Asistida Por Computador S.A.S, NIT 811004721-2).
   - Datos del Representante Legal Principal (Guillermo Humberto Cañón Sarria, C.C. 98555384 de Envigado).
   - Información Financiera y Bancaria (Bancolombia, Cuenta de Ahorros 00300833888).
   - Referencias Comerciales / Bancarias (completar ÚNICAMENTE el primer renglón / Fila 1).
   - Datos de Contacto Principal (Guillermo Humberto Cañón Sarria / Representante Legal).
   - Declaraciones de Origen Lícito de Fondos, SARLAFT, SAGRILAFT y Autorización de Habeas Data / Centrales de Riesgo.

2. **ZONAS ROJAS (IGNORAR TOTALMENTE / NO ESCRIBIR NADA):**
   - Espacio Reservado para la Entidad / Uso Exclusivo del Banco / Aprobación Interna de Riesgos.
   - Datos de la Contraparte / Comprador / Emisor del formato.
   - Declaraciones de Extranjeros / FATCA / CRS cuando aplique solo a no residentes.
   - Personas Expuestas Políticamente (PEP) / Vínculos PEP (dejar completamente vacío).
   - Filas secundarias (Fila 2, 3, 4, 5) en tablas de accionistas o referencias.
   - Casillas 'Otra', 'Otro' o listas genéricas de opciones múltiples.

3. **ZONAS AMARILLAS (DECLARACIONES BINARIAS):**
   - Tipo de Empresa: 'PRIVADA'.
   - Gran Contribuyente: 'NO' | Autorretenedor: 'NO' | Responsable IVA: 'SI'.
   - ¿Maneja recursos públicos?: 'NO' | ¿Es PEP?: 'NO' o dejar vacío.
   - Origen de Fondos: 'Giro ordinario de las actividades comerciales y de servicios de ingeniería'.

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
