export interface ComponentGeneratorSchema {
  /** The name of the component (e.g., Button, Input, Badge) */
  name: string;
  /** Comma-separated variants in format 'variantName:value1,value2' */
  variants?: string;
  /** Comma-separated boolean modifiers */
  modifiers?: string;
  /** Comma-separated slot names */
  slots?: string;
  /** Default HTML element for root */
  rootElement?:
    | 'div'
    | 'span'
    | 'button'
    | 'input'
    | 'label'
    | 'a'
    | 'section'
    | 'article'
    | 'header'
    | 'footer'
    | 'nav'
    | 'aside'
    | 'main';
  /** Use Base UI primitive */
  useBaseUI?: boolean;
  /** Base UI primitive name */
  baseUIPrimitive?: string;
  /** Is compound component */
  isCompound?: boolean;
  /** Export from public API */
  isPublic?: boolean;
  /** Support polymorphism */
  supportsPolymorphism?: boolean;
  /** Subdirectory within components */
  directory?: string;
  /** Skip test generation */
  skipTests?: boolean;
  /** Skip story generation */
  skipStory?: boolean;
}
