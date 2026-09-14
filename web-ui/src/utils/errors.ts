/**
 * Extract a human-readable message from a caught value of unknown type.
 *
 * `catch` clauses receive `unknown`, not `Error` — fetches can reject with
 * a plain string, a DOMException, or other non-Error values, so reading
 * `.message` off an `any`-typed catch variable can throw at runtime if the
 * thrown value has no such property.
 */
export function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
