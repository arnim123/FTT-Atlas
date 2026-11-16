import { Leaf } from 'lucide-react';
export function MockDocument({ title, content }: {
  title: string;
  content: string;
}) {
  const sections = content.split('\n\n').filter(Boolean);
  const inventory = title.toLowerCase().includes('inventory');
  return <article className="paper mx-auto min-h-[760px] w-full max-w-[740px] rounded-sm px-7 py-9 sm:px-12 sm:py-12">
    <div className="mb-10 flex items-center justify-between border-b border-[#dae3d9] pb-4">
      <span className="flex items-center gap-1.5 text-[9px] font-medium tracking-[1px] text-[#507461]"><Leaf size={12} />ATLAS KNOWLEDGE</span>
      <span className="text-[8px] uppercase tracking-widest text-[#8b968c]">A shared resource</span>
    </div>
    <p className="mb-3 text-[9px] font-semibold uppercase tracking-[1.7px] text-[#789382]">YOUR GUIDE TO BETTER WORK</p>
    <h1 className="text-[30px] font-semibold leading-tight tracking-[-.8px] text-[#264737]">{title}</h1>
    <p className="mt-4 text-[11px] leading-relaxed text-[#869087]">Prepared for the Acme team · Internal knowledge resource</p>
    <div className="my-7 h-1 w-12 rounded-full bg-[#699376]" />
    {sections.slice(1).map((section, index) => {
      const [heading, ...lines] = section.split('\n'); return <section key={index} className="mb-6">
        <h2 className="mb-2 text-[14px] font-semibold tracking-tight text-[#375440]">{heading}</h2>
        {lines.map((line, j) => <p className="my-1.5 whitespace-pre-wrap text-[11px] leading-[1.9] text-[#6c766d]" key={j}>{line}</p>)}
        {inventory && heading === 'Inventory management' && <table className="my-5 w-full text-left text-[9px]">
          <thead className="bg-[#ecf1e9]">
            <tr>{['Workflow', 'Frequency', 'Responsible team'].map(label => <th className="p-2.5 font-medium text-[#56705a]" key={label}>{label}</th>)}</tr>
          </thead>
          <tbody>{[['Cycle count', 'Weekly', 'Operations'], ['Stock reconciliation', 'Monthly', 'Warehouse'], ['Reorder review', 'Daily', 'Procurement']].map(row => <tr key={row[0]} className="border-b border-[#e4e9df]">{row.map(cell => <td key={cell} className="p-2.5 text-[#6c766d]">{cell}</td>)}</tr>)}</tbody>
        </table>}
      </section>;
    })}
    <div className="mt-8 border-t border-[#e4e9df] pt-4 text-[8px] text-[#98a294]">ACME WORKSPACE <span className="float-right">Company knowledge · 1</span></div>
  </article>;
}
