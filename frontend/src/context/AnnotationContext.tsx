import { createContext, useContext, useCallback, useRef, ReactNode } from 'react';

interface FieldRegistration {
  name: string;
  getValue: () => any;
}

interface AnnotationCtx {
  registerField: (field: FieldRegistration) => void;
  unregisterField: (name: string) => void;
  getAnnotations: () => Record<string, any>;
}

const AnnotationContext = createContext<AnnotationCtx>(null!);

export function AnnotationProvider({ children }: { children: ReactNode }) {
  const fieldsRef = useRef<Map<string, () => any>>(new Map());

  const registerField = useCallback((field: FieldRegistration) => {
    fieldsRef.current.set(field.name, field.getValue);
  }, []);

  const unregisterField = useCallback((name: string) => {
    fieldsRef.current.delete(name);
  }, []);

  const getAnnotations = useCallback(() => {
    const result: Record<string, any> = {};
    for (const [name, getValue] of fieldsRef.current.entries()) {
      result[name] = getValue();
    }
    return result;
  }, []);

  return (
    <AnnotationContext.Provider value={{ registerField, unregisterField, getAnnotations }}>
      {children}
    </AnnotationContext.Provider>
  );
}

export const useAnnotationContext = () => useContext(AnnotationContext);
