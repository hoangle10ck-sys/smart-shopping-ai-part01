export function AvailabilityBadge({ value }: { value?: string | null }) {
  const normalized = (value || '').split('/').pop()!.toLowerCase().replaceAll('_', ' ');
  const available = ['in stock', 'instock', 'available', 'còn hàng', 'con hang'].includes(normalized);
  const unavailable = ['out of stock', 'outofstock', 'unavailable', 'sold out', 'hết hàng', 'het hang', 'discontinued'].includes(normalized);
  return <span className={`tag ${available ? 'tag-green' : unavailable ? 'tag-red' : ''}`}>{available ? 'Còn hàng' : unavailable ? 'Hết hàng' : 'Chưa rõ tồn kho'}</span>;
}
