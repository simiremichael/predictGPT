'use strict';

/* eslint-disable */
import { findHostInstance } from './platform-specific/findHostInstance';
import { ReanimatedError } from "./errors.js";
export function getShadowNodeWrapperFromRef(ref, hostInstance) {
  const resolvedInstance = hostInstance?.__internalInstanceHandle ?? ref?.__internalInstanceHandle ?? ref?.getNativeScrollRef?.()?.__internalInstanceHandle ?? (ref._reactInternals && findHostInstance(ref).__internalInstanceHandle);
  if (!resolvedInstance) {
    throw new ReanimatedError('Failed to find host instance for a ref.');
  }
  return resolvedInstance.stateNode.node;
}
//# sourceMappingURL=fabricUtils.js.map