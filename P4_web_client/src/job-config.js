export const MODULE_JOB_SCHEMAS = [
  ["proced.xsd", "proced.xsd"],
  ["process.xsd", "process.xsd"],
  ["descript.xsd", "descript.xsd"],
  ["schedul.xsd", "schedul.xsd"],
  ["container.xsd", "container.xsd"],
  ["crew.xsd", "crew.xsd"],
];

const MODULE_JOB_CONFIG = {
  pack_modules: {
    title: "Pack modules",
    submitLabel: "Pack",
    defaultLabel: "pack modules",
  },
  unpack_modules: {
    title: "Unpack modules",
    submitLabel: "Unpack",
    defaultLabel: "unpack modules",
  },
};

export function getModuleJobConfig(kind) {
  return MODULE_JOB_CONFIG[kind] || null;
}

export function isModuleJob(kind) {
  return Boolean(getModuleJobConfig(kind));
}
