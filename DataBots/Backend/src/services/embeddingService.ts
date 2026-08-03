import { Settings } from "llamaindex";

/**
 * Generates a 384-dimensional vector embedding for a given text input.
 * Uses LlamaIndex Settings.embedModel if available, with a fast deterministic hash fallback.
 */
export async function generateTextEmbedding(text: string): Promise<number[]> {
  if (!text) {
    return new Array(384).fill(0);
  }

  try {
    if (Settings.embedModel && typeof (Settings.embedModel as any).getTextEmbedding === "function") {
      const embedding = await (Settings.embedModel as any).getTextEmbedding(text);
      if (Array.isArray(embedding) && embedding.length > 0) {
        return embedding;
      }
    }
  } catch (err) {
    // Fallback to deterministic hash vector generator
  }

  return generateFallbackVector(text, 384);
}

/**
 * Fast deterministic feature hashing vector generator (384 float dimensions, unit L2-normalized)
 */
function generateFallbackVector(text: string, dim = 384): number[] {
  const vec = new Array(dim).fill(0);
  const words = text.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);

  words.forEach((word, idx) => {
    let hash = 0;
    for (let i = 0; i < word.length; i++) {
      hash = (hash << 5) - hash + word.charCodeAt(i);
      hash |= 0;
    }
    const targetIdx = Math.abs(hash) % dim;
    const sign = hash % 2 === 0 ? 1 : -1;
    vec[targetIdx] += sign * (1 / (idx + 1));
  });

  // Calculate L2 norm
  let sqSum = 0;
  for (let i = 0; i < dim; i++) {
    sqSum += vec[i] * vec[i];
  }
  const norm = Math.sqrt(sqSum) || 1;

  for (let i = 0; i < dim; i++) {
    vec[i] = Math.round((vec[i] / norm) * 10000) / 10000;
  }

  return vec;
}
