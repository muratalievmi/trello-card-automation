import { Entity, EntityId, Component, ComponentType, EntityTemplate } from './types.js';

let nextId = 0;

export function generateId(): EntityId {
  return `e_${++nextId}`;
}

export function resetIdCounter(): void {
  nextId = 0;
}

export function createEntity(template: EntityTemplate): Entity {
  const entity: Entity = {
    id: generateId(),
    components: new Map(),
    tags: new Set(template.tags),
  };

  for (const component of template.components) {
    entity.components.set(component.type, structuredClone(component));
  }

  return entity;
}

export function getComponent<T = Record<string, unknown>>(
  entity: Entity,
  type: ComponentType
): T | undefined {
  const comp = entity.components.get(type);
  return comp ? (comp.data as T) : undefined;
}

export function setComponent(entity: Entity, component: Component): void {
  entity.components.set(component.type, structuredClone(component));
}

export function removeComponent(entity: Entity, type: ComponentType): boolean {
  return entity.components.delete(type);
}

export function hasComponent(entity: Entity, type: ComponentType): boolean {
  return entity.components.has(type);
}

export function hasTag(entity: Entity, tag: string): boolean {
  return entity.tags.has(tag);
}

export function addTag(entity: Entity, tag: string): void {
  entity.tags.add(tag);
}

export function removeTag(entity: Entity, tag: string): boolean {
  return entity.tags.delete(tag);
}

export function hasAllComponents(entity: Entity, types: ComponentType[]): boolean {
  return types.every((t) => entity.components.has(t));
}
