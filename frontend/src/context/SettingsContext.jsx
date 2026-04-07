import { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react';
import { getTranslations } from '../i18n';

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [lang, setLangState] = useState(() => localStorage.getItem('corvin_lang') || 'it');
  const [theme, setThemeState] = useState(() => localStorage.getItem('corvin_theme') || 'light');

  const setLang = useCallback((l) => {
    setLangState(l);
    localStorage.setItem('corvin_lang', l);
  }, []);

  const setTheme = useCallback((t) => {
    setThemeState(t);
    localStorage.setItem('corvin_theme', t);
  }, []);

  const toggleLang = useCallback(() => setLang(lang === 'it' ? 'en' : 'it'), [lang, setLang]);
  const toggleTheme = useCallback(() => setTheme(theme === 'light' ? 'dark' : 'light'), [theme, setTheme]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const translations = useMemo(() => getTranslations(lang), [lang]);

  const t = useCallback((key, params) => {
    let str = translations[key] ?? key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
      });
    }
    return str;
  }, [translations]);

  return (
    <SettingsContext.Provider value={{ lang, theme, t, setLang, setTheme, toggleLang, toggleTheme }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
