/**
 * Color manipulation utilities
 * HSL-based color system for Linear-inspired design
 * @module tokens/utils/color-utils
 */

import type { ColorToken, HSLColor, RGBColor } from '../types';

/**
 * Default color scale steps following DevRev/Linear pattern
 * 80 (lightest) to 1000 (darkest) for fine-grained control
 */
export const DEFAULT_COLOR_STEPS = [
  80, 100, 120, 140, 160, 180, 200, 220, 240, 280, 320, 360, 400, 480, 560, 620, 700, 740, 780, 820,
  860, 880, 900, 920, 940, 960, 980, 1000,
] as const;

export type ColorStep = (typeof DEFAULT_COLOR_STEPS)[number];

/**
 * Creates a type-safe color token from HSL values
 *
 * @param h - Hue (0-360)
 * @param s - Saturation (0-100)
 * @param l - Lightness (0-100)
 * @param description - Optional description for documentation
 * @returns ColorToken with HSL metadata
 *
 * @example
 * const primaryColor = createColorToken(235, 56, 60, 'Primary accent');
 */
export function createColorToken(
  h: number,
  s: number,
  l: number,
  description?: string,
): ColorToken {
  return {
    $type: 'color',
    $value: `hsl(${h} ${s}% ${l}%)`,
    $hsl: { h, s, l },
    ...(description && { $description: description }),
  };
}

/**
 * Creates a color token with alpha channel
 *
 * @param h - Hue (0-360)
 * @param s - Saturation (0-100)
 * @param l - Lightness (0-100)
 * @param a - Alpha (0-1)
 * @param description - Optional description
 * @returns ColorToken with HSLA value
 */
export function createColorTokenWithAlpha(
  h: number,
  s: number,
  l: number,
  a: number,
  description?: string,
): ColorToken {
  return {
    $type: 'color',
    $value: `hsla(${h} ${s}% ${l}% / ${a})`,
    $hsl: { h, s, l, a },
    ...(description && { $description: description }),
  };
}

/**
 * Generates a complete color scale from HSL base values
 * Scale: 80 (lightest) to 1000 (darkest)
 *
 * @param name - Color name for the scale (e.g., 'neutral', 'accent')
 * @param hue - Base hue value (0-360)
 * @param saturation - Base saturation value (0-100)
 * @param options - Configuration options
 * @returns Record of step-keyed ColorTokens
 *
 * @example
 * const neutralScale = generateColorScale('neutral', 228, 6);
 * // neutralScale['neutral-100'], neutralScale['neutral-200'], etc.
 */
export function generateColorScale(
  name: string,
  hue: number,
  saturation: number,
  options?: {
    steps?: readonly number[];
    lightnessRange?: { min: number; max: number };
  },
): Record<string, ColorToken> {
  const steps = options?.steps ?? DEFAULT_COLOR_STEPS;
  const { min: minL = 0, max: maxL = 92 } = options?.lightnessRange ?? {};

  return Object.fromEntries(
    steps.map((step) => {
      // Map step (80-1000) to lightness (maxL-minL)
      // Lower step = higher lightness (lighter color)
      const normalizedStep = (step - 80) / (1000 - 80);
      const lightness = Math.round(maxL - normalizedStep * (maxL - minL));

      return [
        `${name}-${step}`,
        createColorToken(hue, saturation, lightness, `${name} at step ${step} (L: ${lightness}%)`),
      ];
    }),
  );
}

/**
 * Converts HSL to RGB color values
 *
 * @param hsl - HSL color object
 * @returns RGB color object with values 0-255
 */
export function hslToRgb(hsl: HSLColor): RGBColor {
  const { h, s, l, a } = hsl;
  const sNorm = s / 100;
  const lNorm = l / 100;

  const c = (1 - Math.abs(2 * lNorm - 1)) * sNorm;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = lNorm - c / 2;

  let r = 0,
    g = 0,
    b = 0;

  if (h >= 0 && h < 60) {
    r = c;
    g = x;
    b = 0;
  } else if (h >= 60 && h < 120) {
    r = x;
    g = c;
    b = 0;
  } else if (h >= 120 && h < 180) {
    r = 0;
    g = c;
    b = x;
  } else if (h >= 180 && h < 240) {
    r = 0;
    g = x;
    b = c;
  } else if (h >= 240 && h < 300) {
    r = x;
    g = 0;
    b = c;
  } else {
    r = c;
    g = 0;
    b = x;
  }

  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255),
    ...(a !== undefined && { a }),
  };
}

/**
 * Converts RGB to HSL color values
 *
 * @param rgb - RGB color object
 * @returns HSL color object
 */
export function rgbToHsl(rgb: RGBColor): HSLColor {
  const r = rgb.r / 255;
  const g = rgb.g / 255;
  const b = rgb.b / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;

  let h = 0;
  let s = 0;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / d + 2) / 6;
        break;
      case b:
        h = ((r - g) / d + 4) / 6;
        break;
    }
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
    ...(rgb.a !== undefined && { a: rgb.a }),
  };
}

/**
 * Converts HSL color to hexadecimal string
 *
 * @param hsl - HSL color object
 * @returns Hex color string (e.g., '#5E6AD2')
 */
export function hslToHex(hsl: HSLColor): string {
  const rgb = hslToRgb(hsl);
  const toHex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`.toUpperCase();
}

/**
 * Parses a hex color string to HSL
 *
 * @param hex - Hex color string (with or without #)
 * @returns HSL color object or null if invalid
 */
export function hexToHsl(hex: string): HSLColor | null {
  const cleanHex = hex.replace('#', '');

  if (!/^[0-9A-Fa-f]{6}$/.test(cleanHex)) {
    return null;
  }

  const r = parseInt(cleanHex.slice(0, 2), 16);
  const g = parseInt(cleanHex.slice(2, 4), 16);
  const b = parseInt(cleanHex.slice(4, 6), 16);

  return rgbToHsl({ r, g, b });
}

/**
 * Adjusts the lightness of an HSL color
 *
 * @param hsl - Original HSL color
 * @param amount - Amount to adjust (-100 to 100)
 * @returns New HSL color with adjusted lightness
 */
export function adjustLightness(hsl: HSLColor, amount: number): HSLColor {
  return {
    ...hsl,
    l: Math.max(0, Math.min(100, hsl.l + amount)),
  };
}

/**
 * Adjusts the saturation of an HSL color
 *
 * @param hsl - Original HSL color
 * @param amount - Amount to adjust (-100 to 100)
 * @returns New HSL color with adjusted saturation
 */
export function adjustSaturation(hsl: HSLColor, amount: number): HSLColor {
  return {
    ...hsl,
    s: Math.max(0, Math.min(100, hsl.s + amount)),
  };
}

/**
 * Creates a CSS HSL string from HSL values
 *
 * @param hsl - HSL color object
 * @returns CSS hsl() or hsla() string
 */
export function toHslString(hsl: HSLColor): string {
  const { h, s, l, a } = hsl;
  if (a !== undefined && a < 1) {
    return `hsla(${h} ${s}% ${l}% / ${a})`;
  }
  return `hsl(${h} ${s}% ${l}%)`;
}

/**
 * Mixes two HSL colors
 *
 * @param color1 - First color
 * @param color2 - Second color
 * @param weight - Weight of first color (0-1, default 0.5)
 * @returns Mixed HSL color
 */
export function mixColors(color1: HSLColor, color2: HSLColor, weight = 0.5): HSLColor {
  const w = Math.max(0, Math.min(1, weight));

  return {
    h: Math.round(color1.h * w + color2.h * (1 - w)),
    s: Math.round(color1.s * w + color2.s * (1 - w)),
    l: Math.round(color1.l * w + color2.l * (1 - w)),
  };
}
