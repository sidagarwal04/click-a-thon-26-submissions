/**
 * CRUD Generator Schema Types
 */

export interface CrudGeneratorSchema {
  /** Entity name (e.g., 'product', 'user') */
  name: string;
  /** Directory to generate files in */
  directory: string;
  /** Import path for data model types */
  dataModel: string;
  /** Base API endpoint (e.g., '/api/products') */
  endpoint: string;
  /** ID field name on the entity */
  idField?: string;
  /** Generate infinite query for list */
  pagination?: boolean;
  /** Skip generating list hook */
  skipList?: boolean;
  /** Skip generating detail hook */
  skipDetail?: boolean;
  /** Skip generating create mutation */
  skipCreate?: boolean;
  /** Skip generating update mutation */
  skipUpdate?: boolean;
  /** Skip generating delete mutation */
  skipDelete?: boolean;
}
