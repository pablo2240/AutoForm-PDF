import React, { useRef } from 'react';
import type { ItemStyle } from '../types';
import { 
  Type, 
  ALargeSmall, 
  Bold, 
  AlignLeft,
  AlignCenter,
  AlignRight,
  Palette, 
  Edit3, 
  Image as ImageIcon,
  Plus,
  Minus
} from 'lucide-react';

interface ToolbarProps {
  currentStyle: ItemStyle;
  onStyleChange: (updates: Partial<ItemStyle>) => void;
  selectedBoxId: string | null;
  selectedBoxLabel: string | null;
  selectedBoxText: string;
  onTextChange: (newText: string) => void;
  onAddText: () => void;
  isTextMode: boolean;
  onAddImage: (base64: string, filename: string) => void;
  isImageMode: boolean;
}

const POPULAR_FONTS = [
  { id: 'Arial', label: 'Arial' },
  { id: 'Calibri', label: 'Calibri' },
  { id: 'Helvetica', label: 'Helvetica' },
  { id: 'Times New Roman', label: 'Times New Roman' },
];

const PRESET_COLORS = [
  { hex: '#000000', label: 'Negro' },
  { hex: '#002060', label: 'Azul Oscuro' },
  { hex: '#1d4ed8', label: 'Azul' },
  { hex: '#b91c1c', label: 'Rojo' },
  { hex: '#15803d', label: 'Verde' },
];

export const Toolbar: React.FC<ToolbarProps> = ({
  currentStyle,
  onStyleChange,
  selectedBoxId,
  selectedBoxLabel,
  selectedBoxText,
  onTextChange,
  onAddText,
  isTextMode,
  onAddImage,
  isImageMode,
}) => {
  const imageInputRef = useRef<HTMLInputElement>(null);
  const colorInputRef = useRef<HTMLInputElement>(null);

  const handleImageFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          onAddImage(reader.result, file.name);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const currentFont = currentStyle.font_family || 'Arial';
  const currentSize = currentStyle.font_size || 10;
  const isBold = currentStyle.bold || false;
  const currentAlign = currentStyle.align || 'left';
  const currentColor = currentStyle.color || '#000000';

  return (
    <div className="editor-secondary-toolbar">
      {/* 1. Fuente */}
      <div className="toolbar-section">
        <div className="toolbar-item" title="Familia tipográfica">
          <Type size={16} className="toolbar-icon" />
          <select 
            className="toolbar-select font-select"
            value={currentFont}
            onChange={(e) => onStyleChange({ font_family: e.target.value })}
            style={{ fontFamily: currentFont }}
          >
            {POPULAR_FONTS.map((f) => (
              <option key={f.id} value={f.id} style={{ fontFamily: f.id }}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="toolbar-divider" />

      {/* 2. Tamaño de fuente con stepper */}
      <div className="toolbar-section">
        <div className="toolbar-item" title="Tamaño de fuente">
          <ALargeSmall size={16} className="toolbar-icon" />
          <button 
            className="btn-toolbar-stepper"
            onClick={() => onStyleChange({ font_size: Math.max(6, currentSize - 1) })}
            title="Disminuir tamaño"
          >
            <Minus size={12} />
          </button>
          <span className="font-size-display">{currentSize} pt</span>
          <button 
            className="btn-toolbar-stepper"
            onClick={() => onStyleChange({ font_size: Math.min(36, currentSize + 1) })}
            title="Aumentar tamaño"
          >
            <Plus size={12} />
          </button>
        </div>
      </div>

      <div className="toolbar-divider" />

      {/* 3. Negrilla (Bold) */}
      <div className="toolbar-section">
        <button 
          className={`btn-toolbar-toggle ${isBold ? 'active' : ''}`}
          onClick={() => onStyleChange({ bold: !isBold })}
          title="Negrilla (Bold)"
        >
          <Bold size={16} />
          <span>B</span>
        </button>
      </div>

      <div className="toolbar-divider" />

      {/* 4. Alineación Horizontal (Izquierda, Centro, Derecha) */}
      <div className="toolbar-section">
        <div className="toolbar-btn-group" title="Alineación del texto">
          <button 
            type="button"
            className={`btn-toolbar-toggle ${currentAlign === 'left' ? 'active' : ''}`}
            onClick={() => onStyleChange({ align: 'left' })}
            title="Alinear a la izquierda"
          >
            <AlignLeft size={15} />
          </button>
          <button 
            type="button"
            className={`btn-toolbar-toggle ${currentAlign === 'center' ? 'active' : ''}`}
            onClick={() => onStyleChange({ align: 'center' })}
            title="Centrar texto"
          >
            <AlignCenter size={15} />
          </button>
          <button 
            type="button"
            className={`btn-toolbar-toggle ${currentAlign === 'right' ? 'active' : ''}`}
            onClick={() => onStyleChange({ align: 'right' })}
            title="Alinear a la derecha"
          >
            <AlignRight size={15} />
          </button>
        </div>
      </div>

      <div className="toolbar-divider" />

      {/* 5. Color */}
      <div className="toolbar-section">
        <div className="toolbar-item" title="Color del texto">
          <Palette size={16} className="toolbar-icon" />
          <div className="color-palette-group">
            {PRESET_COLORS.map((c) => (
              <button 
                key={c.hex}
                className={`color-swatch ${currentColor.toLowerCase() === c.hex.toLowerCase() ? 'active' : ''}`}
                style={{ backgroundColor: c.hex }}
                onClick={() => onStyleChange({ color: c.hex })}
                title={c.label}
              />
            ))}
            <input 
              type="color" 
              ref={colorInputRef}
              value={currentColor} 
              onChange={(e) => onStyleChange({ color: e.target.value })}
              className="custom-color-input"
              title="Color personalizado"
            />
          </div>
        </div>
      </div>

      <div className="toolbar-divider" />

      {/* 6. Editar Texto */}
      <div className="toolbar-section flex-grow">
        <div className="toolbar-item w-full" title="Editar texto del recuadro">
          <Edit3 size={15} className="toolbar-icon" />
          <input 
            type="text"
            className="toolbar-text-input"
            placeholder={selectedBoxId ? `Editar valor de ${selectedBoxLabel || 'campo'}...` : 'Selecciona un cuadro para editar su texto...'}
            value={selectedBoxText}
            onChange={(e) => onTextChange(e.target.value)}
            disabled={!selectedBoxId}
          />
          {selectedBoxId && (
            <span className="badge-selected-field">
              {selectedBoxLabel || 'Seleccionado'}
            </span>
          )}
        </div>
      </div>

      <div className="toolbar-divider" />

      {/* 7. Añadir Texto Libre */}
      <div className="toolbar-section">
        <button 
          type="button"
          className={`btn-toolbar-action btn-toolbar-text ${isTextMode ? 'active-text-mode' : ''}`}
          onClick={onAddText}
          title="Añadir texto libre o personalizado en el documento"
        >
          <Type size={16} />
          <span>{isTextMode ? 'Dibujando Texto...' : 'Añadir Texto'}</span>
        </button>
      </div>

      <div className="toolbar-divider" />

      {/* 8. Agregar Imagen */}
      <div className="toolbar-section">
        <input 
          type="file" 
          ref={imageInputRef} 
          style={{ display: 'none' }} 
          accept="image/png, image/jpeg, image/webp" 
          onChange={handleImageFile}
        />
        <button 
          type="button"
          className={`btn-toolbar-action ${isImageMode ? 'active-image-mode' : ''}`}
          onClick={() => imageInputRef.current?.click()}
          title="Subir imagen para estampar en el PDF"
        >
          <ImageIcon size={16} />
          <span>{isImageMode ? 'Estampando Imagen...' : 'Agregar Imagen'}</span>
        </button>
      </div>
    </div>
  );
};
