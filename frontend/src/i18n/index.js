import it from './it';
import en from './en';

const translations = { it, en };

export function getTranslations(lang) {
  return translations[lang] ?? translations.it;
}

export { it, en };
