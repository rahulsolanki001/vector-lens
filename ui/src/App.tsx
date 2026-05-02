import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { QueryDebugger } from "./panels/QueryDebugger";
import { IndexHealth } from "./panels/IndexHealth";
import { EvalRunner } from "./panels/EvalRunner";
import { VectorExplorer } from "./panels/VectorExplorer";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/debug" replace />} />
          <Route path="/debug"   element={<QueryDebugger />} />
          <Route path="/health"  element={<IndexHealth />} />
          <Route path="/eval"    element={<EvalRunner />} />
          <Route path="/explore" element={<VectorExplorer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
