import { EvalRunner } from "./panels/EvalRunner";
import { IndexHealth } from "./panels/IndexHealth";
import { QueryDebugger } from "./panels/QueryDebugger";
import { VectorExplorer } from "./panels/VectorExplorer";

export function App() {
  return (
    <main>
      <QueryDebugger />
      <VectorExplorer />
      <IndexHealth />
      <EvalRunner />
    </main>
  );
}
