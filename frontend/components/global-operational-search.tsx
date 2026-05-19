"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchOperationalSearch, type OperationalSearchResult } from "@/lib/operational-search";

const SEARCH_DELAY_MS = 250;
const RECENT_SEARCHES_KEY = "omms_recent_operational_searches";

function formatModuleLabel(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function loadRecentSearches() {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    return JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function storeRecentSearch(query: string) {
  if (typeof window === "undefined" || !query.trim()) {
    return;
  }
  const nextSearches = [query.trim(), ...loadRecentSearches().filter((item) => item !== query.trim())].slice(0, 5);
  window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(nextSearches));
}

export function GlobalOperationalSearch() {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const [moduleFilter, setModuleFilter] = useState("");
  const [results, setResults] = useState<OperationalSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  const groupedResults = useMemo(() => {
    return results.reduce<Record<string, OperationalSearchResult[]>>((grouped, item) => {
      grouped[item.module] = [...(grouped[item.module] ?? []), item];
      return grouped;
    }, {});
  }, [results]);

  useEffect(() => {
    setRecentSearches(loadRecentSearches());
  }, []);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const payload = await fetchOperationalSearch({ q: trimmed, modules: moduleFilter });
        setResults(payload.results);
        storeRecentSearch(trimmed);
        setRecentSearches(loadRecentSearches());
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [moduleFilter, query]);

  function selectRecentSearch(value: string) {
    setQuery(value);
    setIsOpen(true);
  }

  return (
    <div className="global-search" ref={wrapperRef}>
      <div className="global-search-row">
        <input
          aria-label="Search operations"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder="Search campaigns, POEs, jobs, alerts..."
        />
        <select
          aria-label="Search module"
          value={moduleFilter}
          onChange={(event) => {
            setModuleFilter(event.target.value);
            setIsOpen(true);
          }}
        >
          <option value="">All</option>
          <option value="campaigns">Campaigns</option>
          <option value="poes">POE</option>
          <option value="jobs">Jobs</option>
          <option value="alerts">Alerts</option>
          <option value="sites,units">Inventory</option>
          <option value="invoices,clients">Finance</option>
        </select>
      </div>

      {isOpen ? (
        <div className="global-search-popover">
          {query.trim().length < 2 ? (
            <div className="global-search-empty">
              <strong>Operational search</strong>
              <span>Type at least two characters to search scoped OMMS records.</span>
              {recentSearches.length ? (
                <div className="recent-searches">
                  {recentSearches.map((item) => (
                    <button key={item} type="button" onClick={() => selectRecentSearch(item)}>
                      {item}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {isLoading ? <p className="global-search-empty">Searching...</p> : null}

          {!isLoading && query.trim().length >= 2 && results.length === 0 ? (
            <p className="global-search-empty">No matching operational records found.</p>
          ) : null}

          {!isLoading && results.length > 0 ? (
            <div className="global-search-groups">
              {Object.entries(groupedResults).map(([module, items]) => (
                <section key={module}>
                  <p className="global-search-group-title">{formatModuleLabel(module)}</p>
                  {items.map((item) => (
                    <Link
                      className="global-search-result"
                      href={item.url || "/operations"}
                      key={`${item.module}-${item.id}`}
                      onClick={() => setIsOpen(false)}
                    >
                      <span className="module-badge">{formatModuleLabel(item.module)}</span>
                      <strong>{item.title}</strong>
                      <small>{item.subtitle}</small>
                      {item.status ? <em>{formatModuleLabel(item.status)}</em> : null}
                    </Link>
                  ))}
                </section>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
