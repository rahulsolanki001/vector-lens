import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { getConfig, getCollections } from "../../api/client";
import { useVaraStore } from "../../store";

export function Layout() {
  const { setBackends, setCollections, setBackendName, setCollectionName, backends } =
    useVaraStore();

  useEffect(() => {
    async function bootstrap() {
      try {
        const [config, collections] = await Promise.all([getConfig(), getCollections()]);
        setBackends(config.backends);
        setCollections(collections);

        // Auto-select first backend + collection if only one exists
        if (config.backends.length === 1) {
          setBackendName(config.backends[0].name);
        }
        if (collections.length === 1) {
          setCollectionName(collections[0].name);
        }
      } catch {
        // Server may not be running yet; silently ignore
      }
    }
    bootstrap();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-full bg-bg-base">
      <TopBar />
      <Sidebar />
      <main className="ml-[220px] mt-16 min-h-[calc(100vh-64px)] p-6 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
