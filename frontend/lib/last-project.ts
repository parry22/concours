/** The project the user had open last, so the app reopens it. Per browser only; a missing value is fine. */
const KEY = "concours:last-project";

export function lastProject(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberProject(id: string): void {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    // private mode or blocked storage: the app still works, it just opens the newest project
  }
}

export function forgetProject(id: string): void {
  try {
    if (window.localStorage.getItem(KEY) === id) window.localStorage.removeItem(KEY);
  } catch {
    // see above
  }
}
