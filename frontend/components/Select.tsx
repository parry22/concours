"use client";

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { cx } from "./ui";

export type SelectOption = {
  value: string;
  label: string;
  /** A sample value from the data, shown muted on the right. */
  detail?: string;
  /** Shown instead of the detail when the option cannot be picked, e.g. "Used for Amount". */
  disabledReason?: string;
  tag?: string;
};

const SEARCH_FROM = 8; // options; below this a filter box is noise
const MENU_MAX = 288; // px

/**
 * A listbox select. The trigger shows the chosen option and its sample value; the menu lists every option with
 * its sample, marks the chosen one, and explains disabled ones. Keyboard: arrows move, Enter picks, Escape
 * closes, typing filters (long lists). Opens upward when there is no room below.
 */
export function Select({
  value,
  options,
  onChange,
  placeholder,
  emptyOption,
  invalid,
  id,
  ariaLabel,
}: {
  value: string | null;
  options: SelectOption[];
  onChange: (value: string | null) => void;
  placeholder: string;
  /** A first option that clears the choice ("Not in my file"). */
  emptyOption?: string;
  invalid?: boolean;
  id?: string;
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [up, setUp] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const uid = useId();
  const listId = `${uid}-list`;

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const opts = q ? options.filter((o) => o.label.toLowerCase().includes(q) || (o.detail ?? "").toLowerCase().includes(q)) : options;
    return emptyOption && !q ? [{ value: "", label: emptyOption } as SelectOption, ...opts] : opts;
  }, [options, query, emptyOption]);
  const current = options.find((o) => o.value === value) ?? null;
  const showSearch = options.length >= SEARCH_FROM;

  function openMenu() {
    const r = button.current?.getBoundingClientRect();
    if (r) setUp(window.innerHeight - r.bottom < MENU_MAX + 16 && r.top > window.innerHeight - r.bottom);
    setQuery("");
    const i = items.findIndex((o) => o.value === (value ?? ""));
    setActive(i >= 0 ? i : 0);
    setOpen(true);
  }

  function close(focus = true) {
    setOpen(false);
    if (focus) button.current?.focus();
  }

  function pick(o: SelectOption) {
    if (o.disabledReason) return;
    onChange(o.value || null);
    close();
  }

  function step(dir: 1 | -1) {
    if (!items.length) return;
    let i = active;
    for (let n = 0; n < items.length; n++) {
      i = (i + dir + items.length) % items.length;
      if (!items[i].disabledReason) break;
    }
    setActive(i);
  }

  function onKey(e: KeyboardEvent) {
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        openMenu();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      step(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      step(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(items.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (items[active]) pick(items[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Tab") {
      close(false);
    }
  }

  // close on outside press
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) close(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  // focus the filter (or the list) on open, keep the active row in view
  useLayoutEffect(() => {
    if (!open) return;
    (showSearch ? searchRef.current : list.current)?.focus();
  }, [open, showSearch]);
  useLayoutEffect(() => {
    if (!open) return;
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, items.length - 1)));
  }, [items.length]);

  return (
    <div ref={root} className="relative min-w-0" onKeyDown={onKey}>
      <button
        ref={button}
        id={id}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel}
        onClick={() => (open ? close() : openMenu())}
        className={cx(
          "group flex h-11 w-full min-w-0 items-center gap-2.5 rounded-xl border bg-card-2 pr-2.5 pl-3 text-left transition-[border-color,background-color,box-shadow] duration-150",
          "hover:border-[#3a3a40] focus-visible:border-accent/70 focus-visible:ring-2 focus-visible:ring-accent/20 focus-visible:outline-none",
          open ? "border-accent/60 ring-2 ring-accent/15" : invalid ? "border-danger/45" : "border-border-strong",
        )}
      >
        {current ? (
          <>
            <span className="num min-w-0 shrink truncate text-[13px] text-foreground">{current.label}</span>
            {current.detail ? <span className="num min-w-0 flex-1 truncate text-[12px] text-muted">{current.detail}</span> : <span className="flex-1" />}
            {current.tag ? <span className="shrink-0 rounded-md bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium text-accent">{current.tag}</span> : null}
          </>
        ) : (
          <span className={cx("flex-1 truncate text-[13px]", invalid ? "text-subtle" : "text-muted")}>{value === null && emptyOption ? emptyOption : placeholder}</span>
        )}
        <ChevronDown className={cx("h-4 w-4 shrink-0 text-muted transition-transform duration-150 group-hover:text-subtle", open && "rotate-180")} aria-hidden />
      </button>

      {open ? (
        <div
          className={cx(
            "select-pop absolute right-0 left-0 z-40 min-w-[260px] overflow-hidden rounded-xl border border-border-strong bg-[#161618] shadow-[0_18px_50px_-12px_rgb(0_0_0/0.75)]",
            up ? "bottom-[calc(100%+6px)] origin-bottom" : "top-[calc(100%+6px)] origin-top",
          )}
        >
          {showSearch ? (
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                placeholder="Filter columns"
                aria-label="Filter columns"
                aria-controls={listId}
                aria-activedescendant={items[active] ? `${uid}-${active}` : undefined}
                className="h-10 min-w-0 flex-1 bg-transparent text-[13px] placeholder:text-muted"
                style={{ outline: "none" }} // the menu's border shows focus; the global ring would box the field
              />
            </div>
          ) : null}
          <ul
            ref={list}
            id={listId}
            role="listbox"
            tabIndex={-1}
            aria-activedescendant={items[active] ? `${uid}-${active}` : undefined}
            className="scroll-thin overflow-y-auto p-1"
            style={{ maxHeight: MENU_MAX - (showSearch ? 40 : 0), outline: "none" }}
          >
            {items.length === 0 ? <li className="px-3 py-2.5 text-[12px] text-muted">No column matches</li> : null}
            {items.map((o, i) => {
              const selected = (value ?? "") === o.value;
              const disabled = Boolean(o.disabledReason);
              return (
                <li
                  key={o.value || "__empty"}
                  id={`${uid}-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={selected}
                  aria-disabled={disabled}
                  onPointerMove={() => !disabled && setActive(i)}
                  onClick={() => pick(o)}
                  className={cx(
                    "flex min-h-9 cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px]",
                    i === active && !disabled && "bg-card-3",
                    disabled && "cursor-not-allowed",
                    !o.value && "text-subtle",
                  )}
                >
                  <span className="flex w-4 shrink-0 justify-center">{selected ? <Check className="icon-brand h-3.5 w-3.5" strokeWidth={2.5} /> : null}</span>
                  <span className={cx("min-w-0 shrink truncate", o.value && "num", disabled ? "text-muted" : "text-foreground")}>{o.label}</span>
                  {o.tag && !disabled ? <span className="shrink-0 rounded-md bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium text-accent">{o.tag}</span> : null}
                  <span className={cx("ml-auto min-w-0 truncate pl-2 text-right text-[12px]", disabled ? "text-muted/70 italic" : "num text-muted")}>
                    {o.disabledReason ?? o.detail ?? ""}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
