// frontend/components/layouts/AgentPlanningPageLayout.js (Unchanged from previous update)
import React from 'react';

/**
 * AgentPlanningPageLayout Component
 * This component provides the specific layout for the AI planning process,
 * now simplified to be a single, full-screen chat window.
 * It removes the old sidebar layout and acts as a simple container.
 */
const AgentPlanningPageLayout = ({ children }) => {
  return (
    // Main container now centers the child content
    <div className="flex justify-center items-center w-full min-h-screen p-4">
      {children}
    </div>
  );
};

export default AgentPlanningPageLayout;