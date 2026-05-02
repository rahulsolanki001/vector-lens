import { NavLink } from "react-router-dom";
import { Bug, Heart, FlaskConical, Boxes } from "lucide-react";

const NAV = [
  { to: "/debug",   icon: Bug,          label: "Query Debugger" },
  { to: "/health",  icon: Heart,         label: "Index Health"   },
  { to: "/eval",    icon: FlaskConical,  label: "Eval Runner"    },
  { to: "/explore", icon: Boxes,         label: "Vector Explorer"},
];

export function Sidebar() {
  return (
    <aside className="fixed top-16 left-0 bottom-0 z-30 w-[220px] flex flex-col bg-bg-surface border-r border-bg-border overflow-y-auto">
      <nav className="flex flex-col gap-1 p-3 pt-4">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 px-3 py-3 rounded-md text-base transition-colors",
                isActive
                  ? "bg-accent-muted text-accent font-medium"
                  : "text-tx-secondary hover:bg-bg-raised hover:text-tx-primary",
              ].join(" ")
            }
          >
            <Icon size={17} strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
