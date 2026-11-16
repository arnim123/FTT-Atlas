/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_MOCKS?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_ENABLE_TEST_LOGIN?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface Window {
  google?: {
    accounts: {
      id: {
        initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
        renderButton: (parent: HTMLElement, options: { theme?: string; size?: string; width?: number; text?: string }) => void;
      };
    };
  };
}
